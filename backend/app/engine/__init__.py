"""Administration engine: model-agnostic core, strategy contract, registry.

The engine core never branches on administration model. Each model is a
self-contained strategy (``engine/strategies/``) registered via ``registry``.
Adding a model must not edit this package's core, the contract, or siblings.
"""
