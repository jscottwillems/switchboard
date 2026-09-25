"""Request dependencies."""

from fastapi import Request

from switchboard.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container
