from . import db

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)

    template_key = db.Column(db.Text, nullable=False)  # 'request_created', 'slot_booked', ...
    payload_json = db.Column(db.JSON)
    sent_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False, server_default=db.text("NOW()"))

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.id} user={self.user_id} {self.template_key}>"
