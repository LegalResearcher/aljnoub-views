import json
import os
import tempfile

MAX_SUCCESSFUL_ORDERS_PER_LINK = 5
ACCOUNT_COUNT = 3


def read_nonempty_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def load_success_counts(counts_path, done_path):
    """Load durable counts; legacy done links stay complete at the user's request."""
    if not os.path.exists(counts_path):
        return {link: MAX_SUCCESSFUL_ORDERS_PER_LINK for link in read_nonempty_lines(done_path)}

    with open(counts_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("success_counts.json must contain an object")

    counts = {}
    for link, value in data.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Invalid successful-order count for {link}")
        counts[str(link)] = value
    return counts


def save_success_counts(counts_path, counts):
    os.makedirs(os.path.dirname(counts_path), exist_ok=True)
    temporary_path = counts_path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(counts, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary_path, counts_path)


def record_success(link, counts_path, done_path):
    counts = load_success_counts(counts_path, done_path)
    current = counts.get(link, 0)
    if current >= MAX_SUCCESSFUL_ORDERS_PER_LINK:
        return current

    counts[link] = current + 1
    save_success_counts(counts_path, counts)

    if link not in read_nonempty_lines(done_path):
        os.makedirs(os.path.dirname(done_path), exist_ok=True)
        with open(done_path, "a", encoding="utf-8") as file:
            file.write(link + "\n")
    return counts[link]


def select_rotating_account(environ, state_dir):
    """Select one configured account and persist which account is next.

    The cursor is shared by scheduled and manual workflows through state/.
    Credentials are returned to the caller and are never written to disk.
    """
    accounts = []
    missing = []
    for number in range(1, ACCOUNT_COUNT + 1):
        username = environ.get(f"SITE_USERNAME_{number}", "").strip()
        password = environ.get(f"SITE_PASSWORD_{number}", "")
        if not username:
            missing.append(f"SITE_USERNAME_{number}")
        if not password:
            missing.append(f"SITE_PASSWORD_{number}")
        accounts.append((username, password))
    if missing:
        raise ValueError("Missing required secrets: " + ", ".join(missing))

    os.makedirs(state_dir, exist_ok=True)
    cursor_path = os.path.join(state_dir, "account_rotation.json")
    next_account = 1
    if os.path.exists(cursor_path):
        with open(cursor_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("account_rotation.json must contain an object")
        next_account = data.get("next_account", 1)
        if (not isinstance(next_account, int) or isinstance(next_account, bool)
                or not 1 <= next_account <= ACCOUNT_COUNT):
            raise ValueError("Invalid next_account in account_rotation.json")

    selected = next_account
    following = selected % ACCOUNT_COUNT + 1
    fd, temporary_path = tempfile.mkstemp(prefix=".account-rotation-", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"next_account": following}, file)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, cursor_path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)

    username, password = accounts[selected - 1]
    return selected, username, password
