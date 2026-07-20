# Data Model

Darwin stores raw exchange messages for auditability and normalized objects for trading/research.

UTC timestamps are used internally. Both exchange timestamps and local receipt timestamps should be preserved when available.

The initial storage model includes raw JSON messages with indexes by exchange, event type, and receipt timestamp.
