class Config:
    """Global configuration, populated from CLI args at startup."""

    log_dir: str = "logs"
    debug: bool = False
    fps: float = 100.0

    # Network ports
    RPC_PORT: int = 10667
    VIS_PORT: int = 18888
