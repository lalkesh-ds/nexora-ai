import logging 
def setup_loggger(name ='medical_assitant'):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)


    formatter = logging.Formatter("[%(asctime)s][%(levelname)s] --- [%(message)s]")
    ch.setFormatter(formatter)

    if not logger.hasHandlers():
        logger.addHandler(ch)

    return logger

logger = setup_loggger()
logger.info("rag process started")    
logger.info("debudding")
logger.error("failed to load")
logger.critical("critical message")