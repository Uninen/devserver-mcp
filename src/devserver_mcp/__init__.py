__version__ = "0.6.0"


def main():
    """Main entry point that routes to new CLI."""
    from .cli import cli

    cli()


if __name__ == "__main__":
    main()
