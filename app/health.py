from flask_restful import Resource


class Health(Resource):
    """Sin autenticación: lo consultan los health checks de Beanstalk / ALB."""

    def get(self):
        return {"status": "ok"}, 200
