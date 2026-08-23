"""Data models for Phase 3 phone application features."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class CallDirection(Enum):
    """Call direction."""
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class CallStatus(Enum):
    """Call status."""
    CALLING = "calling"
    ANSWERED = "answered"
    MISSED = "missed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CallRecord:
    """A single call history record."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    number: str = ""  # Phone number or SIP URI
    contact_id: Optional[str] = None
    direction: CallDirection = CallDirection.OUTGOING
    status: CallStatus = CallStatus.CANCELLED
    started_at: datetime = field(default_factory=datetime.now)
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration: int = 0  # Duration in seconds (only for answered calls)
    sip_account: str = ""  # SIP account/provider name used
    
    @property
    def is_answered(self) -> bool:
        return self.status == CallStatus.ANSWERED
    
    @property
    def is_incoming(self) -> bool:
        return self.direction == CallDirection.INCOMING
    
    @property
    def formatted_duration(self) -> str:
        """Format duration as MM:SS or HH:MM:SS."""
        if self.duration <= 0:
            return "00:00"
        minutes = self.duration // 60
        seconds = self.duration % 60
        if minutes >= 60:
            hours = minutes // 60
            minutes = minutes % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "number": self.number,
            "contact_id": self.contact_id,
            "direction": self.direction.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration": self.duration,
            "sip_account": self.sip_account,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CallRecord":
        """Create from dictionary."""
        record = cls(
            id=data.get("id", str(uuid.uuid4())),
            number=data.get("number", ""),
            contact_id=data.get("contact_id"),
            direction=CallDirection(data.get("direction", "outgoing")),
            status=CallStatus(data.get("status", "cancelled")),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.now(),
            answered_at=datetime.fromisoformat(data["answered_at"]) if data.get("answered_at") else None,
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            duration=data.get("duration", 0),
            sip_account=data.get("sip_account", ""),
        )
        return record


@dataclass
class Contact:
    """A contact in the address book."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    number: str = ""  # Phone number or SIP URI
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "number": self.number,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Contact":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            number=data.get("number", ""),
            notes=data.get("notes", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
        )


@dataclass
class PhoneSettings:
    """Phone application settings."""
    
    default_sip_account: str = ""  # Provider name
    audio_input_device: str = ""  # Device ID or empty for default
    audio_output_device: str = ""  # Device ID or empty for default
    show_call_duration: bool = True
    auto_answer_enabled: bool = False
    ringtone: str = "default"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "default_sip_account": self.default_sip_account,
            "audio_input_device": self.audio_input_device,
            "audio_output_device": self.audio_output_device,
            "show_call_duration": self.show_call_duration,
            "auto_answer_enabled": self.auto_answer_enabled,
            "ringtone": self.ringtone,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PhoneSettings":
        """Create from dictionary."""
        return cls(
            default_sip_account=data.get("default_sip_account", ""),
            audio_input_device=data.get("audio_input_device", ""),
            audio_output_device=data.get("audio_output_device", ""),
            show_call_duration=data.get("show_call_duration", True),
            auto_answer_enabled=data.get("auto_answer_enabled", False),
            ringtone=data.get("ringtone", "default"),
        )