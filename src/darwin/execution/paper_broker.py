from darwin.execution.simulated_broker import SimulatedBroker


class PaperBroker(SimulatedBroker):
    """Live-data broker that simulates fills locally and never submits to an exchange."""
