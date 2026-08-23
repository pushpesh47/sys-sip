"""Persistence layer for Phase 3 phone application features."""

import json
import threading
from pathlib import Path
from typing import Optional
from app.data.models import CallRecord, Contact, PhoneSettings, CallDirection, CallStatus
from datetime import datetime


class DataStore:
    """JSON-based persistent storage for call history, contacts, and settings."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / ".config" / "sys-sip"
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self._call_history_file = self.config_dir / "call_history.json"
        self._contacts_file = self.config_dir / "contacts.json"
        self._settings_file = self.config_dir / "phone_settings.json"
        
        self._lock = threading.RLock()
        self._call_history: list[CallRecord] = []
        self._contacts: list[Contact] = []
        self._settings: PhoneSettings = PhoneSettings()
        
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all data from disk."""
        with self._lock:
            self._call_history = self._load_call_history()
            self._contacts = self._load_contacts()
            self._settings = self._load_settings()
    
    def _load_call_history(self) -> list[CallRecord]:
        """Load call history from file."""
        if not self._call_history_file.exists():
            return []
        try:
            with open(self._call_history_file, 'r') as f:
                data = json.load(f)
                return [CallRecord.from_dict(item) for item in data]
        except Exception:
            return []
    
    def _save_call_history(self) -> None:
        """Save call history to file."""
        try:
            data = [record.to_dict() for record in self._call_history]
            with open(self._call_history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Silently fail on save error
    
    def _load_contacts(self) -> list[Contact]:
        """Load contacts from file."""
        if not self._contacts_file.exists():
            return []
        try:
            with open(self._contacts_file, 'r') as f:
                data = json.load(f)
                return [Contact.from_dict(item) for item in data]
        except Exception:
            return []
    
    def _save_contacts(self) -> None:
        """Save contacts to file."""
        try:
            data = [contact.to_dict() for contact in self._contacts]
            with open(self._contacts_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    
    def _load_settings(self) -> PhoneSettings:
        """Load settings from file."""
        if not self._settings_file.exists():
            return PhoneSettings()
        try:
            with open(self._settings_file, 'r') as f:
                data = json.load(f)
                return PhoneSettings.from_dict(data)
        except Exception:
            return PhoneSettings()
    
    def _save_settings(self) -> None:
        """Save settings to file."""
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(self._settings.to_dict(), f, indent=2)
        except Exception:
            pass
    
    # Call History Methods
    def add_call_record(self, record: CallRecord) -> None:
        """Add a call record to history."""
        with self._lock:
            self._call_history.insert(0, record)  # Most recent first
            self._save_call_history()
    
    def get_call_history(self, limit: Optional[int] = None) -> list[CallRecord]:
        """Get call history, most recent first."""
        with self._lock:
            if limit:
                return self._call_history[:limit]
            return self._call_history.copy()
    
    def get_recent_calls(self, limit: int = 10) -> list[CallRecord]:
        """Get recent calls for quick access."""
        with self._lock:
            return self._call_history[:limit]
    
    def find_call_record(self, record_id: str) -> Optional[CallRecord]:
        """Find a call record by ID."""
        with self._lock:
            for record in self._call_history:
                if record.id == record_id:
                    return record
            return None
    
    def update_call_record(self, record: CallRecord) -> None:
        """Update an existing call record."""
        with self._lock:
            for i, existing in enumerate(self._call_history):
                if existing.id == record.id:
                    self._call_history[i] = record
                    self._save_call_history()
                    return
    
    def clear_call_history(self) -> None:
        """Clear all call history."""
        with self._lock:
            self._call_history.clear()
            self._save_call_history()
    
    # Contact Methods
    def add_contact(self, contact: Contact) -> None:
        """Add a new contact."""
        with self._lock:
            self._contacts.append(contact)
            self._save_contacts()
    
    def get_contacts(self) -> list[Contact]:
        """Get all contacts, sorted by name."""
        with self._lock:
            return sorted(self._contacts, key=lambda c: c.name.lower())
    
    def get_contact(self, contact_id: str) -> Optional[Contact]:
        """Get a contact by ID."""
        with self._lock:
            for contact in self._contacts:
                if contact.id == contact_id:
                    return contact
            return None
    
    def _digits_only(self, value: str) -> str:
        """Return only digit characters from the string."""
        return ''.join(ch for ch in value if ch.isdigit())

    def _numbers_match(self, a: str, b: str) -> bool:
        """Check if two phone numbers represent the same subscriber.
        Handles variants like 0xxxxxxxxxx vs +91xxxxxxxxxx by comparing the last 10 digits.
        For non-phone (e.g., SIP URIs), falls back to exact digit-string equality.
        """
        da = self._digits_only(a)
        db = self._digits_only(b)
        if len(da) >= 10 and len(db) >= 10:
            return da[-10:] == db[-10:]
        return da == db

    def find_contact_by_number(self, number: str) -> Optional[Contact]:
        """Find a contact by phone number/SIP URI using flexible matching."""
        with self._lock:
            for contact in self._contacts:
                if self._numbers_match(contact.number, number):
                    return contact
            return None
    
    def search_contacts(self, query: str) -> list[Contact]:
        """Search contacts by name or number."""
        with self._lock:
            query = query.lower().strip()
            if not query:
                return self.get_contacts()
            results = []
            for contact in self._contacts:
                if query in contact.name.lower() or query in contact.number.lower():
                    results.append(contact)
            return sorted(results, key=lambda c: c.name.lower())
    
    def update_contact(self, contact: Contact) -> None:
        """Update an existing contact."""
        with self._lock:
            contact.updated_at = datetime.now()
            for i, existing in enumerate(self._contacts):
                if existing.id == contact.id:
                    self._contacts[i] = contact
                    self._save_contacts()
                    return
    
    def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact by ID."""
        with self._lock:
            for i, contact in enumerate(self._contacts):
                if contact.id == contact_id:
                    self._contacts.pop(i)
                    self._save_contacts()
                    return True
            return False
    
    # Settings Methods
    def get_settings(self) -> PhoneSettings:
        """Get current settings."""
        with self._lock:
            return self._settings
    
    def update_settings(self, settings: PhoneSettings) -> None:
        """Update settings."""
        with self._lock:
            self._settings = settings
            self._save_settings()


# Global instance
_store_instance: Optional[DataStore] = None
_store_lock = threading.Lock()


def get_data_store(config_dir: Optional[Path] = None) -> DataStore:
    """Get the global data store instance."""
    global _store_instance
    with _store_lock:
        if _store_instance is None:
            _store_instance = DataStore(config_dir)
        return _store_instance