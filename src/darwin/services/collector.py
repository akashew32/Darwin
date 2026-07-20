class CollectorService:
    def __init__(self) -> None:
        self.running = False

    async def run_once(self) -> str:
        return "collector_ready"
