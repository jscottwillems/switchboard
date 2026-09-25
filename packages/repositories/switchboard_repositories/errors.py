"""Repository failures that are not database driver errors."""


class RepositoryError(Exception):
    pass


class NotFound(RepositoryError):
    pass


class StateConflict(RepositoryError):
    """A mutable status column cannot move in that direction."""


class InvalidCursor(RepositoryError):
    pass
