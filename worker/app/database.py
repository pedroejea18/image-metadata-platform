"""PostgreSQL operations shared by the local and Lambda workers."""

import psycopg2

from common.settings import postgres_options


def get_connection():
    return psycopg2.connect(**postgres_options())


def get_filename(image_id: int) -> str:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT filename FROM images WHERE id = %s", (image_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Image {image_id} does not exist")
            return row[0]
    finally:
        connection.close()


def complete_image(image_id: int, width: int, height: int, camera_model: str | None):
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE images SET width = %s, height = %s,
                       camera_model = %s, processed_at = CURRENT_TIMESTAMP,
                       status = 'completed' WHERE id = %s""",
                    (width, height, camera_model, image_id),
                )
    finally:
        connection.close()


def fail_image(image_id: int):
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE images SET status = 'failed' WHERE id = %s", (image_id,)
                )
    finally:
        connection.close()
