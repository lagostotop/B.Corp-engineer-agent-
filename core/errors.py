"""Application errors and Flask error handlers."""

import logging

from flask import jsonify

logger = logging.getLogger("brain3.errors")


class AppError(Exception):
    status_code = 400
    code = "APP_ERROR"

    def __init__(self, message, status_code=None, code=None, details=None):
        super().__init__(message)
        self.message = message

        if status_code is not None:
            self.status_code = status_code

        if code is not None:
            self.code = code

        self.details = details


class ValidationError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class AuthorizationError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTH_REQUIRED"


class ServiceError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        body = {
            "error": {
                "code": error.code,
                "message": error.message
            }
        }

        if error.details is not None:
            body["error"]["details"] = error.details

        return jsonify(body), error.status_code

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": "Resource not found."
            }
        }), 404

    @app.errorhandler(405)
    def handle_405(error):
        return jsonify({
            "error": {
                "code": "METHOD_NOT_ALLOWED",
                "message": "Method not allowed."
            }
        }), 405

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        logger.exception("Unhandled application error")

        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred."
            }
        }), 500