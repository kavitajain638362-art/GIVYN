# GIVYN

Personal Color Analysis Expert System

## Run the web app on Windows

From the project folder, start Flask in one PowerShell window. Follow the backend setup below first for a fresh checkout.

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app run
```

In a second PowerShell window, run the React frontend. Use Node 20.19+, 22.12+, or a current supported release. The local setup uses Node 24.

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run dev
```

Open [GIVYN on localhost](http://127.0.0.1:5173/). The frontend proxies `/api` to Flask on port 5000. Upload, drag in, or capture a portrait, optionally enter natural hair and eye colors, then give consent and select **Check and analyze**. Passing photos produce a palette with explanations. Open **Color studio** to compare colors, metals, or virtual drapes and **My analyses** to manage history or download a PDF. Camera capture requires browser permission and a secure context such as localhost or HTTPS.

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run preview
```

The preview serves the built app on port 4173 with the same Flask proxy. The React frontend lives in `frontend/src` and uses Tailwind with locally bundled fonts. The landing page uses Instrument Serif and DM Sans. Inner pages use Libre Baskerville for large headings and Cormorant Garamond for smaller headings, body text, and controls. The landing garden artwork is stored in `frontend/src/assets/givyn-garden.webp`.

## Deploy on Vercel

Import the repository root as one [Vercel Services project](https://vercel.com/docs/services). The `frontend` service serves the Vite site at `/`. The Express `gateway` service accepts same-origin `/api/*` requests and forwards them to `app`, the internal Flask service. The gateway reads `GIVYN_API_URL` at request time from its Vercel service binding. Model training runs offline via `python -m training.train`.

Run the Services project from the repository root without linking or deploying:

```powershell
# Use a Python 3.14 environment from the local setup below.
. .\.venv\Scripts\Activate.ps1
python backend/fetch_models.py
npm.cmd --prefix frontend ci
npm.cmd --prefix gateway ci
npx.cmd vercel@66.2.0 dev --local --listen 3000
```

Open `http://localhost:3000/` and `http://localhost:3000/api/health`. Refresh a frontend route such as `/history` to check deep linking. The separate Flask and Vite commands above still work with local SQLite and the Vite development proxy.

From the Vercel project's **Storage** tab, create or connect a [Neon Marketplace database](https://vercel.com/marketplace/neon). The integration supplies the pooled `DATABASE_URL` to Flask on Vercel. Connect it to Production and enable Neon preview branches if you use Preview deployments. `GIVYN_DATABASE_URL` remains available as an explicit override and for local PostgreSQL testing. Flask creates the workspace tables on first use. If hosted storage is missing, workspace requests return `503`. Existing local SQLite history is separate from Neon.

The cloud build verifies and bundles the pinned MediaPipe models and the three native GL dispatch libraries its Linux wheel requires for CPU inference. Linux builds use headless OpenCV. Vercel photo uploads are limited to 4 MiB per photo to leave room for multipart fields within the [Function payload limit](https://vercel.com/docs/functions/limitations#request-body-size). Local standalone Flask and Vite retain the 10 MiB limit.

Before publishing, smoke-test a preview with the database configured. Check `/api/health`, upload a consented test portrait, reload the results, download its PDF and verify deletion in history. The bundled seasonal model is licensed for research use as described in [the training notes](training/README.md).

## Photo validation and analysis API

GIVYN accepts a consented JPG, JPEG or PNG portrait and checks whether it is usable for personal color analysis. The Flask API uses Google’s [MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker?tab=Python) to detect a face and mark the forehead and both cheeks. OpenCV and NumPy measure blur, exposure clipping and the difference in brightness between the two cheeks.

### Set up on Windows

Run these PowerShell commands from the project folder. Use a 64-bit Python installation. The local setup uses Python 3.14 and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt

New-Item -ItemType Directory -Path backend\models -Force | Out-Null
curl.exe --fail --location --output backend\models\face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
curl.exe --fail --location --output backend\models\selfie_multiclass_256x256.tflite https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/1/selfie_multiclass_256x256.tflite

.\.venv\Scripts\python.exe -m flask --app backend.app run
```

The server listens on `http://127.0.0.1:5000`. Set `GIVYN_FACE_MODEL` or `GIVYN_GARMENT_MODEL` to absolute paths to use models stored elsewhere. `/api/health` checks for the face model file. Test a portrait to verify the model loads and runs.

```powershell
curl.exe http://127.0.0.1:5000/api/health
curl.exe -F "consent=true" -F "image=@C:\path\to\portrait.jpg" http://127.0.0.1:5000/api/images/validate
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### API contract

`POST /api/images/validate` takes exactly one multipart `image` and `consent=true`. Files up to 10 MiB and 24 megapixels are accepted. A successful check returns HTTP `200` with `status: "valid"`, image dimensions, usable skin sampling polygons, photo guidance, advisory `warnings`, and image-quality measurements. Severe blur or an unusable face returns `422` with `status: "retake"` and actionable `issues`. Low resolution, tight framing, moderate head angles, and poor lighting are advisory and allow analysis with lower confidence. The focus measurement is normalized for exposure. In a group photo, GIVYN uses the largest usable face among up to five detections and includes that selection in the warnings.

Malformed requests, unsupported formats, size limits and unavailable model files return `status: "error"` and an `error` object with a stable `code` and a user-facing `message`. Limits and thresholds are initial heuristics. Cheek brightness differences can have causes besides shadows, and a passing face mesh cannot establish that each skin region is fully visible. The capture guidance covers heavy makeup and beauty filters because the app does not reliably detect them.

Uploads are processed locally in memory. GIVYN discards the photo at the end of the request and sends `Cache-Control: no-store`. The browser temporarily holds the portrait for preview and draping. **Remove photo** clears the upload preview, consent, and feedback. **Remove portrait** clears the draping preview.

### Personal workspace endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /api/analyses` | Accepts the same upload and consent fields, plus optional `hair` and `eyes` as HEX and `observation` as `warm`, `cool`, or `mixed`. Validates photo first, then saves measurements and returns the palette. |
| `GET /api/analyses/<id>` | Returns a saved analysis and palette for the current profile. |
| `DELETE /api/analyses/<id>` | Deletes the analysis, its palette and related comparisons. |
| `GET /api/colors/options` | Lists color-pair and metal presets. |
| `POST /api/analyses/<id>/comparisons` | Accepts a JSON `mode` and `colors` array. Use one HEX for `compatibility`, two for `comparison` or `draping`, and an empty array for `metals`. Scores and records the comparison. |
| `GET /api/history` | Lists analyses, favorite HEX colors and the latest 30 comparisons. |
| `DELETE /api/history` | Clears all saved data for the current profile. |
| `POST /api/favorites` | Saves a JSON swatch with `name` and `hex`. |
| `DELETE /api/favorites/<six digits>` | Removes a favorite by HEX without the leading hash. |
| `GET /api/analyses/<id>/report.pdf` | Downloads the analysis, palette, explanations, and recent comparisons. |

The SQLite database defaults to `instance/givyn.sqlite3`. Set `GIVYN_DATABASE` to change the path. An anonymous browser profile uses an HTTP-only cookie to scope access. The same browser retains history across restarts. Clearing its cookie removes access to that profile, so use **Delete all saved data** when you want to remove the records themselves. The database stores measurements, palettes, favorites, and comparisons. Original photos and draping landmarks are held temporarily and excluded from saved analysis records.

### Backend modules

| Module | Purpose |
| --- | --- |
| `backend/app.py` | Configures Flask, limits request size, checks consent and returns JSON responses. |
| `backend/images.py` | Checks the file extension and decoded format, caps dimensions, applies EXIF orientation and converts embedded profiles to sRGB. |
| `backend/face.py` | Runs the MediaPipe face mesh and maps the forehead and cheeks. |
| `backend/validation.py` | Applies framing, pose, exposure and blur checks and reports measurements and retake guidance. |
| `backend/colors.py` | Extracts trimmed RGB samples, calculates HSV and CIE Lab, matches Monk reference lightness, and samples visible irises when the samples agree. |
| `backend/inference.py` | Coordinates measurements, undertone/contrast heuristics, trained seasonal inference, palette rules and color comparisons. |
| `backend/seasonal_model.py` | Runs the portable learned JSON classifier, checks measurement sensitivity and reports model provenance and uncertainty. |
| `training/train.py` | Audits source feature data, splits supplied identities, trains candidates and exports evaluation results. |
| `backend/knowledge_base.json` | Versioned seasonal profiles, reference swatches, presets, thresholds and explanatory IF-THEN rules. |
| `backend/workspace.py` | Serves analysis, comparison, history, favorite, deletion and report endpoints. |
| `backend/storage.py` | Stores scoped SQLite profiles, analysis history, palettes, favorites and comparisons. |
| `backend/report.py` | Builds the downloadable ReportLab PDF in memory. |
| `backend/draping.py` | Runs multiclass portrait segmentation once per upload for skin/hair sampling and a transient fabric mask. |

### How the estimates work

- Skin depth uses the closest CIE L* among the ten Monk reference swatches. Undertone combines Lab yellow/red balance (70%) and HSV hue (30%) across forehead and cheek samples. Patch agreement influences confidence, and optional drape observations contribute to the final warm/cool tendency. These outputs are estimates of appearance under the photo’s lighting and processing.
- Facial contrast uses the range of available CIE L* values across skin, hair, and eyes. High-confidence hair pixels near the selected head are sampled automatically; a manual natural-hair swatch overrides them. Iris sampling has a quality gate and can be overridden. Sources are shown with the measurements. Skin sampling uses forehead and cheek polygons with a face-skin mask when reliable.
- Seasonal inference now uses a locally trained, experimental classifier on skin and hair CIE Lab means. It does **not** equate high contrast or dark hair with Winter. Skin-only predictions are explicitly weak evidence. Results show alternative seasons, model support, source-feature test metrics, out-of-range warnings and deterministic sensitivity checks. Model support is not personal accuracy. Undertone and contrast remain separate heuristics; they do not override learned probabilities. Old saved analyses retain their original results. Re-analyze to use the new model.
- The included research model was trained on 1,182 rows, selected/calibrated on 358 validation rows and tested on 387 rows with disjoint normalized supplied identities. Its skin-and-hair feature accuracy is **44.96%**, top-two accuracy **76.23%**; skin-only accuracy is **29.20%**. These are source-feature benchmarks, **not end-to-end GIVYN photo accuracy**. The model is tentative, research-use only, and coverage across men and skin depths is unverified. See [training data, limitations and reproduction](training/README.md) and [full evaluation](training/evaluation.json). User photos and previous predictions are never used as training data.
- If the trained JSON artifact is missing, an explicitly labeled low-confidence heuristic fallback uses undertone (43%), contrast (28%), saturation (21%), lightness (4%) and brightness (4%), plus knowledge-base rule bonuses. This fallback has not been professionally validated.
- Compatibility uses a weighted combination of nearest favorable swatch proximity by CIEDE2000 (76%), warm or cool tendency (14%), and HSV saturation fit (10%). Scores of 82 or above are highly compatible, 60–81 compatible, and below 60 less harmonious. Metal scores compare a metal’s warm or cool tendency with the undertone estimate and season.
- Virtual draping uses a high-confidence garment mask below the chin from Google's [multiclass portrait segmenter](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Multiclass%20Segmentation.pdf). The browser changes masked fabric pixels and retains the original photo elsewhere. If fabric cannot be identified, or a new local preview photo is chosen, it displays a clearly labeled approximate collar around the original photo. Both previews use the same palette scoring rules.
