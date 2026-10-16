class FakeNotifier:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def notify(self, level: str, msg: str) -> None:
        self.events.append((level, msg))

    def messages(self, level: str | None = None) -> list[str]:
        return [m for lv, m in self.events if level is None or lv == level]
