
from app.modules.user.domain.authorization import AuthorizationContext

class LocalAuthorizationMiddleware:
    def __init__(self, app, authorization_context: AuthorizationContext):  # type: ignore
        self.app = app
        self.authorization_context = authorization_context

    async def __call__(self, scope, receive, send): # type: ignore
        if scope["type"] == "http":
            state = scope.setdefault("state", {})
            state.setdefault("authorization_context", self.authorization_context)

        await self.app(scope, receive, send)
