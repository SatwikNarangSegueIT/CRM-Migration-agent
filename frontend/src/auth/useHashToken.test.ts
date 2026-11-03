import { afterEach, describe, expect, it } from "vitest";
import { readHashToken } from "./useHashToken";

describe("readHashToken", () => {
  afterEach(() => window.history.replaceState(null, "", "/"));

  it("takes the token, clears the fragment and returns it again on later reads", () => {
    window.history.replaceState(null, "", "/accept-invitation?x=1#token=abc123");
    expect(readHashToken()).toBe("abc123");
    expect(window.location.hash).toBe("");
    expect(window.location.search).toBe("?x=1");
    // StrictMode double-invocation / re-mount: the fragment is gone but the token is not lost.
    expect(readHashToken()).toBe("abc123");
  });

  it("keeps tokens per page and prefers a newer link", () => {
    window.history.replaceState(null, "", "/reset-password#token=r1");
    expect(readHashToken()).toBe("r1");
    window.history.replaceState(null, "", "/reset-password#token=r2");
    expect(readHashToken()).toBe("r2");
    window.history.replaceState(null, "", "/somewhere-else");
    expect(readHashToken()).toBe("");
  });
});
