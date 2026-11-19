"""WSGI entry point for the Vercel Flask service."""

from backend.app import create_app

app = create_app()
