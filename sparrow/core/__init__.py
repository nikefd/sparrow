"""Pure domain core: models, the step reducer, budgeting, and schema rendering.

Nothing in this package does I/O or imports a third-party library. The core
talks to the world only through the Protocols in ``sparrow.ports``, which makes
the whole loop unit-testable with fakes and no network.
"""
