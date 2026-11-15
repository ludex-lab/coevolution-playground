//! Append-only claim board sketch — Team OS borrow from [victorkwak/baton](https://github.com/victorkwak/baton).
//!
//! Apache-2.0; concepts derived from upstream @ 965c8dcd1a9bd8d1805c1b9b90284b8471347eba.
//! No git transport, hooks, or upstream crate dependency — directory replay only.

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fmt;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

pub const STALE_AFTER: Duration = Duration::hours(4);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Status {
    Open,
    Working,
    Done,
    Wontdo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeader {
    pub id: String,
    pub posted_at: DateTime<Utc>,
    pub from: String,
    pub to: String,
    pub task: String,
    #[serde(default)]
    pub kind: String,
    pub subject: String,
    #[serde(default)]
    pub body: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatusEvent {
    pub id: String,
    pub at: DateTime<Utc>,
    pub by: String,
    pub msg: String,
    pub status: Status,
}

#[derive(Debug, Clone)]
pub struct MessageView {
    pub header: MessageHeader,
    pub status: Status,
    pub addressee: String,
    pub last_at: DateTime<Utc>,
}

#[derive(Debug)]
pub enum BoardError {
    Io(io::Error),
    Json(serde_json::Error),
    Rule(String),
}

impl fmt::Display for BoardError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            BoardError::Io(e) => write!(f, "io: {e}"),
            BoardError::Json(e) => write!(f, "json: {e}"),
            BoardError::Rule(s) => write!(f, "rule: {s}"),
        }
    }
}

impl std::error::Error for BoardError {}

impl From<io::Error> for BoardError {
    fn from(value: io::Error) -> Self {
        BoardError::Io(value)
    }
}

impl From<serde_json::Error> for BoardError {
    fn from(value: serde_json::Error) -> Self {
        BoardError::Json(value)
    }
}

pub type Result<T> = std::result::Result<T, BoardError>;

/// On-disk layout: `messages/<id>.json`, `events/<event-id>.json` (append-only).
pub struct BoardDir {
    root: PathBuf,
}

impl BoardDir {
    pub fn open(root: impl AsRef<Path>) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        fs::create_dir_all(root.join("messages"))?;
        fs::create_dir_all(root.join("events"))?;
        Ok(Self { root })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn post_message(&self, header: MessageHeader) -> Result<()> {
        let path = self.root.join("messages").join(format!("{}.json", header.id));
        if path.exists() {
            return Err(BoardError::Rule(format!("duplicate message id {}", header.id)));
        }
        let data = serde_json::to_vec_pretty(&header)?;
        fs::write(path, data)?;
        Ok(())
    }

    /// Append a status event file (never overwrite). Returns the event id written.
    pub fn append_status_event(&self, event: StatusEvent) -> Result<String> {
        let path = self
            .root
            .join("events")
            .join(format!("{}.json", event.id));
        if path.exists() {
            return Err(BoardError::Rule(format!("duplicate event id {}", event.id)));
        }
        let id = event.id.clone();
        let data = serde_json::to_vec_pretty(&event)?;
        fs::write(path, data)?;
        Ok(id)
    }

    pub fn load_views(&self, now: DateTime<Utc>) -> Result<Vec<MessageView>> {
        let headers = self.load_messages()?;
        let events = self.load_events_sorted()?;
        Ok(replay_state(headers, &events, now, false)?.into_values().collect())
    }

    pub fn inbox_lines(&self, machine: &str, now: DateTime<Utc>) -> Result<Vec<String>> {
        let views = self.load_views(now)?;
        let mut lines = vec!["# id\tfrom\tto\ttask\tkind\tstatus\tage\tstale".to_string()];
        for v in views {
            if !inbox_actionable(&v, machine) {
                continue;
            }
            let age = format_age(now - v.last_at);
            let stale = is_stale(&v, now);
            lines.push(format!(
                "{}\t{}\t{}\t{}\t{}\t{:?}\t{}\t{}",
                v.header.id,
                v.header.from,
                v.header.to,
                v.header.task,
                v.header.kind,
                status_label(v.status),
                age,
                stale
            ));
        }
        Ok(lines)
    }

    pub fn try_take(&self, msg_id: &str, by: &str, event_id: &str, now: DateTime<Utc>) -> Result<()> {
        let views = self.load_views(now)?;
        let view = views
            .iter()
            .find(|v| v.header.id == msg_id)
            .ok_or_else(|| BoardError::Rule(format!("unknown message {msg_id}")))?;
        validate_status_transition(view, by, Status::Working)?;
        let event = StatusEvent {
            id: event_id.to_string(),
            at: now,
            by: by.to_string(),
            msg: msg_id.to_string(),
            status: Status::Working,
        };
        self.append_status_event(event)?;
        Ok(())
    }

    /// Strict replay: any rule-breaking event (e.g. losing concurrent `take`) is an error.
    pub fn validate_replay(&self, now: DateTime<Utc>) -> Result<()> {
        let headers = self.load_messages()?;
        let events = self.load_events_sorted()?;
        replay_state(headers, &events, now, true)?;
        Ok(())
    }

    fn load_messages(&self) -> Result<BTreeMap<String, MessageHeader>> {
        let mut map = BTreeMap::new();
        let dir = self.root.join("messages");
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }
            let header: MessageHeader = serde_json::from_slice(&fs::read(&path)?)?;
            map.insert(header.id.clone(), header);
        }
        Ok(map)
    }

    fn load_events_sorted(&self) -> Result<Vec<StatusEvent>> {
        let mut events = Vec::new();
        let dir = self.root.join("events");
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }
            let ev: StatusEvent = serde_json::from_slice(&fs::read(&path)?)?;
            events.push(ev);
        }
        events.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(events)
    }
}

fn replay_state(
    headers: BTreeMap<String, MessageHeader>,
    events: &[StatusEvent],
    _seed: DateTime<Utc>,
    strict: bool,
) -> Result<BTreeMap<String, MessageView>> {
    let mut state: BTreeMap<String, MessageView> = headers
        .into_iter()
        .map(|(id, header)| {
            let addressee = header.to.clone();
            (
                id.clone(),
                MessageView {
                    header: header.clone(),
                    status: Status::Open,
                    addressee,
                    last_at: header.posted_at,
                },
            )
        })
        .collect();

    for ev in events {
        let view = state
            .get(&ev.msg)
            .ok_or_else(|| BoardError::Rule(format!("event references missing msg {}", ev.msg)))?
            .clone();
        match validate_status_transition(&view, &ev.by, ev.status) {
            Ok(()) => {
                let entry = state.get_mut(&ev.msg).expect("just looked up");
                entry.status = ev.status;
                entry.last_at = ev.at;
                if entry.header.to == "any" && ev.status == Status::Working {
                    entry.addressee = ev.by.clone();
                }
            }
            Err(e) if strict => return Err(e),
            Err(_) => {}
        }
    }
    Ok(state)
}

pub fn validate_status_transition(view: &MessageView, by: &str, to: Status) -> Result<()> {
    if by != view.addressee && !(view.header.to == "any" && view.status == Status::Open && to == Status::Working) {
        return Err(BoardError::Rule(format!(
            "only addressee {} may transition (by={by})",
            view.addressee
        )));
    }
    let from = view.status;
    let ok = match (from, to) {
        (Status::Open, Status::Working | Status::Done | Status::Wontdo) => true,
        (Status::Working, Status::Done | Status::Wontdo | Status::Open) => true,
        (Status::Done | Status::Wontdo, _) => false,
        _ => false,
    };
    if !ok {
        return Err(BoardError::Rule(format!(
            "invalid transition {:?} -> {:?} on {}",
            from, to, view.header.id
        )));
    }
    Ok(())
}

pub fn is_stale(view: &MessageView, now: DateTime<Utc>) -> bool {
    matches!(view.status, Status::Open | Status::Working)
        && now.signed_duration_since(view.last_at) > STALE_AFTER
}

fn inbox_actionable(view: &MessageView, machine: &str) -> bool {
    match view.status {
        Status::Open => view.addressee == machine || view.header.to == "any",
        Status::Working => view.addressee == machine,
        Status::Done | Status::Wontdo => false,
    }
}

fn status_label(s: Status) -> &'static str {
    match s {
        Status::Open => "open",
        Status::Working => "working",
        Status::Done => "done",
        Status::Wontdo => "wontdo",
    }
}

fn format_age(d: chrono::TimeDelta) -> String {
    if d.num_hours() >= 1 {
        format!("{}h", d.num_hours())
    } else {
        format!("{}m", d.num_minutes())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn temp_board() -> (std::path::PathBuf, BoardDir) {
        let path = std::env::temp_dir().join(format!(
            "claim-board-test-{}-{}",
            std::process::id(),
            Utc::now().timestamp_nanos_opt().unwrap_or(0)
        ));
        let _ = fs::remove_dir_all(&path);
        let board = BoardDir::open(&path).unwrap();
        (path, board)
    }

    fn cleanup(path: &Path) {
        let _ = fs::remove_dir_all(path);
    }

    fn sample_msg(id: &str, to: &str) -> MessageHeader {
        MessageHeader {
            id: id.to_string(),
            posted_at: Utc::now(),
            from: "ork".to_string(),
            to: to.to_string(),
            task: "t1".to_string(),
            kind: String::new(),
            subject: "do thing".to_string(),
            body: "secret body must not appear in inbox".to_string(),
        }
    }

    #[test]
    fn addressee_only_and_done() {
        let (path, board) = temp_board();
        let now = Utc::now();
        board.post_message(sample_msg("m1", "smith")).unwrap();
        board
            .try_take("m1", "smith", "evt001", now)
            .unwrap();
        let err = board.try_take("m1", "ork", "evt002", now);
        assert!(err.is_err());

        board
            .append_status_event(StatusEvent {
                id: "evt003".to_string(),
                at: now,
                by: "smith".to_string(),
                msg: "m1".to_string(),
                status: Status::Done,
            })
            .unwrap();
        let views = board.load_views(now).unwrap();
        assert_eq!(views[0].status, Status::Done);
        cleanup(&path);
    }

    #[test]
    fn inbox_is_header_only() {
        let (path, board) = temp_board();
        let now = Utc::now();
        board.post_message(sample_msg("m1", "smith")).unwrap();
        let lines = board.inbox_lines("smith", now).unwrap();
        let joined = lines.join("\n");
        assert!(!joined.contains("secret body"));
        assert!(joined.contains("m1\tork\tsmith"));
        cleanup(&path);
    }

    #[test]
    fn stale_open_message() {
        let (path, board) = temp_board();
        let old = Utc::now() - Duration::hours(5);
        board
            .post_message(MessageHeader {
                id: "m1".to_string(),
                posted_at: old,
                from: "ork".to_string(),
                to: "smith".to_string(),
                task: "t".to_string(),
                kind: String::new(),
                subject: "s".to_string(),
                body: String::new(),
            })
            .unwrap();
        let views = board.load_views(Utc::now()).unwrap();
        assert!(is_stale(&views[0], Utc::now()));
        cleanup(&path);
    }

    #[test]
    fn concurrent_take_one_wins_no_file_conflict() {
        let (path, board) = temp_board();
        let now = Utc::now();
        board.post_message(sample_msg("m1", "smith")).unwrap();
        board
            .try_take("m1", "smith", "00000000000000000001", now)
            .unwrap();
        // Concurrent push: second machine appended its own event file before re-fetch (no edit conflict).
        board
            .append_status_event(StatusEvent {
                id: "00000000000000000002".to_string(),
                at: now,
                by: "smith".to_string(),
                msg: "m1".to_string(),
                status: Status::Working,
            })
            .unwrap();

        let events_dir = path.join("events");
        assert_eq!(fs::read_dir(&events_dir).unwrap().count(), 2);

        let views = board.load_views(now).unwrap();
        assert_eq!(views[0].status, Status::Working);

        assert!(board.validate_replay(now).is_err());
        cleanup(&path);
    }
}
