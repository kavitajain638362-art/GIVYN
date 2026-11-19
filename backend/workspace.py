"""REST endpoints for analysis, comparison, history and report downloads."""

import hashlib
import re
from secrets import token_urlsafe

from flask import Blueprint, current_app, g, jsonify, request, send_file

from .colors import normalize_hex
from .face import FaceLandmarkerUnavailable
from .images import ImageError
from .validation import validate_faces

COOKIE = "givyn_profile"
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


def _error(code, message, status):
    return jsonify(status="error", error={"code": code, "message": message}), status


def _user():
    token = request.cookies.get(COOKIE, "")
    if not TOKEN.fullmatch(token):
        token = token_urlsafe(32)
        g.givyn_token = token
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_workspace(store, landmarker, segmenter, read_photo):
    api = Blueprint("workspace", __name__, url_prefix="/api")

    @api.after_request
    def private_profile_cookie(response):
        if "givyn_token" in g:
            response.set_cookie(COOKIE, g.givyn_token, max_age=365 * 24 * 3600,
                                httponly=True, samesite="Strict", secure=request.is_secure)
        return response

    @api.post("/analyses")
    def analyze():
        from .inference import analyze_colors

        try:
            photo = read_photo()
            hair = request.form.get("hair") or None
            eyes = request.form.get("eyes") or None
            observation = request.form.get("observation") or None
            hair = normalize_hex(hair) if hair else None
            eyes = normalize_hex(eyes) if eyes else None
            if observation not in {None, "warm", "cool", "mixed"}:
                raise ValueError("Choose a listed drape observation.")
        except ImageError as error:
            return _error(error.code, str(error), error.status)
        except ValueError as error:
            return _error("invalid_color_input", str(error), 400)
        try:
            faces = landmarker.detect(photo)
        except FaceLandmarkerUnavailable as error:
            current_app.logger.error("Face Landmarker unavailable: %s", error)
            return _error("model_unavailable", "Photo analysis is temporarily unavailable.", 503)
        validation = validate_faces(photo, faces)
        if validation["status"] != "valid":
            return jsonify(validation), 422
        probabilities = None
        try:
            probabilities = segmenter.segment(photo)
        except (OSError, RuntimeError, ValueError) as error:
            current_app.logger.warning("Portrait segmentation unavailable: %s", error)
        result = analyze_colors(photo, validation, faces[validation["face_index"]], hair, eyes, observation, probabilities)
        try:
            result["drape_anchor"]["garment_mask"] = segmenter.mask(photo, result["drape_anchor"]["chin"][1], probabilities) if probabilities is not None else None
        except (OSError, RuntimeError, ValueError) as error:
            current_app.logger.warning("Garment preview unavailable: %s", error)
        return jsonify(status="valid", analysis=store.save_analysis(_user(), result),
                       **{key: value for key, value in validation.items() if key != "status"}), 201

    @api.get("/analyses/<int:analysis_id>")
    def get_analysis(analysis_id):
        analysis = store.get_analysis(_user(), analysis_id)
        if analysis is None:
            return _error("analysis_missing", "This analysis could not be found in your history.", 404)
        return jsonify(analysis)

    @api.delete("/analyses/<int:analysis_id>")
    def delete_analysis(analysis_id):
        if not store.delete_analysis(_user(), analysis_id):
            return _error("analysis_missing", "This analysis could not be found in your history.", 404)
        return "", 204

    @api.get("/history")
    def history():
        return jsonify(store.history(_user()))

    @api.delete("/history")
    def delete_history():
        store.delete_profile(_user())
        g.pop("givyn_token", None)
        response = current_app.response_class(status=204)
        response.delete_cookie(COOKIE, httponly=True, samesite="Strict", secure=request.is_secure)
        return response

    @api.post("/favorites")
    def save_color():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _error("invalid_color_input", "Send a HEX color.", 400)
        try:
            color = normalize_hex(body.get("hex"))
            name = body.get("name") or color
            if not isinstance(name, str) or len(name) > 80:
                raise ValueError("Enter a color name with at most 80 characters.")
        except ValueError as error:
            return _error("invalid_color_input", str(error), 400)
        store.save_color(_user(), color, name.strip() or color)
        return "", 204

    @api.delete("/favorites/<hex_value>")
    def delete_color(hex_value):
        try:
            color = normalize_hex("#" + hex_value)
        except ValueError as error:
            return _error("invalid_color_input", str(error), 400)
        store.delete_color(_user(), color)
        return "", 204

    @api.get("/colors/options")
    def color_options():
        from .inference import knowledge

        kb = knowledge()
        return jsonify(comparisons=kb["comparisons"], metals=kb["metals"],
                       seasons={name: entry["description"] for name, entry in kb["seasons"].items()})

    @api.post("/analyses/<int:analysis_id>/comparisons")
    def compare(analysis_id):
        from .inference import compare_color, compare_metals

        user = _user()
        analysis = store.get_analysis(user, analysis_id)
        if analysis is None:
            return _error("analysis_missing", "Start with a portrait analysis.", 404)
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _error("invalid_color_input", "Choose colors to compare.", 400)
        mode = body.get("mode")
        if mode == "metals":
            colors = compare_metals(analysis)
        elif mode in ("compatibility", "comparison", "draping"):
            raw = body.get("colors")
            count = 1 if mode == "compatibility" else 2
            if not isinstance(raw, list) or len(raw) != count:
                return _error("invalid_color_input", f"Choose exactly {count} color(s).", 400)
            try:
                normalized = [normalize_hex(value) for value in raw]
            except ValueError as error:
                return _error("invalid_color_input", str(error), 400)
            colors = [compare_color(value, analysis) for value in normalized]
        else:
            return _error("invalid_mode", "Choose a valid comparison mode.", 400)
        score = max(color["score"] for color in colors)
        winners = [color for color in colors if color["score"] == score]
        answer = {"colors": colors, "winner": winners[0]["hex"] if len(winners) == 1 else None,
                  "tie": len(winners) > 1}
        if not store.save_comparison(user, analysis_id, mode, answer):
            return _error("analysis_missing", "This analysis was removed.", 404)
        return jsonify(answer)

    @api.get("/analyses/<int:analysis_id>/report.pdf")
    def report(analysis_id):
        from .report import analysis_pdf

        user = _user()
        analysis = store.get_analysis(user, analysis_id)
        if analysis is None:
            return _error("analysis_missing", "This analysis could not be found in your history.", 404)
        stream = analysis_pdf(analysis, store.comparisons(user, analysis_id))
        return send_file(stream, mimetype="application/pdf", as_attachment=True,
                         download_name=f"GIVYN-{analysis['season']['name']}-{analysis_id}.pdf")

    return api
