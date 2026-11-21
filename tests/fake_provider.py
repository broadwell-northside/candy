"""Stand-in for the hosted services' HTTP: a session that records every request and answers from a script.
Nothing here touches a network. `calls` is the list of requests made; tests assert it stays empty on a refusal."""
import json


class FakeResponse:
    def __init__(self, status=200, body=None, content=b""):
        self.status_code, self._body, self._content = status, body, content

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body

    def iter_content(self, size):
        for i in range(0, len(self._content), size):
            yield self._content[i:i + size]


class FakeSession:
    """routes: a list of callables (method, url, body) -> FakeResponse | None, tried in order."""

    def __init__(self, clip=b""):
        self.calls = []
        self.clip = clip
        self.task_polls = 0
        self.fail_with = None      # (status, body) to answer every request with
        self.raise_error = None    # an exception to raise on every request
        self.task_status = ["RUNNING", "SUCCEEDED"]
        self.result_url = "https://dashscope-result-sh.oss-cn-shanghai.aliyuncs.com/clip.mp4?Expires=1"

    def request(self, method, url, json=None, headers=None, timeout=None, allow_redirects=True):
        self.calls.append({"method": method, "url": url, "json": json, "headers": dict(headers or {}),
                           "allow_redirects": allow_redirects})
        if self.raise_error:
            raise self.raise_error
        if self.fail_with:
            return FakeResponse(self.fail_with[0], self.fail_with[1])
        if "/video-synthesis" in url:
            return FakeResponse(200, {"output": {"task_id": "0385dc79-5ff8-4d82-bcb6-aaaaaa", "task_status": "PENDING"}})
        if "/api/v1/tasks/" in url:
            status = self.task_status[min(self.task_polls, len(self.task_status) - 1)]
            self.task_polls += 1
            out = {"task_status": status}
            if status == "SUCCEEDED":
                out["video_url"] = self.result_url
            if status == "FAILED":
                out["code"] = "DataInspectionFailed"
            return FakeResponse(200, {"output": out})
        if "chat/completions" in url:
            return FakeResponse(200, {"choices": [{"message": {"content": "hello from the stub"}}]})
        return FakeResponse(404, {"code": "NotFound"})

    def get(self, url, stream=False, timeout=None, allow_redirects=True, headers=None):
        self.calls.append({"method": "GET", "url": url, "json": None, "headers": dict(headers or {}),
                           "allow_redirects": allow_redirects, "download": True})
        return FakeResponse(200, None, self.clip)
