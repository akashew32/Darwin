# Recovery

Live paper trading treats market data health as a trading dependency.

Sequence gap flow:

1. Mark the market as recovering.
2. Stop strategy decisions for that market.
3. Record a health event.
4. Fetch a fresh snapshot from the read-only provider.
5. Replace the local order book.
6. Mark the market healthy after snapshot validation.

Reconnect events increment per-market reconnect metrics and preserve the
subscription intent for the provider. The mock provider emits reconnect and
snapshot-recovery events so this path is exercised without external network
access.

Queue overflow is fail-closed: the bounded event bus raises an overflow error,
the health monitor marks the session halted, and the service writes the final
state during shutdown.

Restart support is partial. `--resume` is accepted and logged, but durable
session reconstruction beyond persisted normalized events remains future work.
