from __future__ import annotations


class ServiceResponse:
    def __init__(self, success, data=None, error=None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self):
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error
        }
