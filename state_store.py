import json
import os

MAX_SUCCESSFUL_ORDERS_PER_LINK = 5


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
