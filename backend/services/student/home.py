import logging
def has_request(user_id) -> bool:
    """
    Check if the user has an appointment.
    """
    from models.user import User
    from models.request import Request

    user = User.query.get(user_id)
    if not user:
        logging.warning(f"User with ID {user_id} not found.")
        return False
    request = Request.query.filter_by(student_id=user.id).first()
    if not request:
        logging.info(f"No appointment found for user ID {user_id}.")
        return False
    return True if request else False