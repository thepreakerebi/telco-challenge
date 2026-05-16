from __future__ import annotations

from huggingface_hub import snapshot_download


REPO_ID = "netop/Telco-Troubleshooting-Agentic-Challenge"


def main() -> None:
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir="data/raw",
        local_dir_use_symlinks=False,
    )
    print("Downloaded dataset into data/raw")


if __name__ == "__main__":
    main()

