use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Unique user identifier assigned at registration.
pub type UserId = Uuid;

/// Session token assigned at login; authenticates subsequent messages.
pub type SessionId = Uuid;

/// Unix timestamp in milliseconds.
pub type Timestamp = u64;

/// Validated username: 1–32 ASCII alphanumeric characters or underscores.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Username(String);

impl Username {
    pub fn new(s: impl Into<String>) -> Result<Self, &'static str> {
        let s = s.into();
        if s.is_empty() || s.len() > 32 {
            return Err("username must be 1–32 characters");
        }
        if !s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
            return Err("username must contain only ASCII letters, digits, or underscores");
        }
        Ok(Self(s))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for Username {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl TryFrom<String> for Username {
    type Error = &'static str;

    fn try_from(s: String) -> Result<Self, Self::Error> {
        Self::new(s)
    }
}

impl TryFrom<&str> for Username {
    type Error = &'static str;

    fn try_from(s: &str) -> Result<Self, Self::Error> {
        Self::new(s)
    }
}
