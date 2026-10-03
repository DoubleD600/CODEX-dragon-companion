from dragon_companion.__main__ import main

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import logging
        logging.exception("Application startup failed")
        raise
