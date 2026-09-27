"""Errors the agent can act on."""


class SkillError(Exception):
    """A failure with a stated cause and the action the agent should take next.

    The CLI prints these as ``Error: <message>`` and ``Next: <next_step>`` instead of a
    traceback. A small model that sees a raw traceback tends to write its own code to work
    around it, which this skill must prevent (decision E0).
    """

    def __init__(self, message: str, next_step: str) -> None:
        super().__init__(message)
        self.message = message
        self.next_step = next_step
