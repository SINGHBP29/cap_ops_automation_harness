import json
import logging

from kafka import KafkaProducer

from app.config import settings

logger = logging.getLogger(__name__)

producer = None


def get_producer():
    global producer

    if producer is not None:
        return producer

    try:
        producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
    except Exception as exc:
        logger.warning("Failed to connect to Kafka: %s", exc)
        producer = None

    return producer


def kafka_is_available():
    active_producer = get_producer()

    if active_producer is None:
        return False

    try:
        return active_producer.bootstrap_connected()
    except Exception as exc:
        logger.warning("Kafka health check failed: %s", exc)
        return False


def publish_signal(signal):
    active_producer = get_producer()

    if active_producer:
        try:
            active_producer.send("ops-signals", signal).get(timeout=10)
            active_producer.flush()
        except Exception as exc:
            logger.error("Failed to publish signal to Kafka: %s", exc)
    else:
        logger.info("Kafka producer not available, skipping signal: %s", signal)
