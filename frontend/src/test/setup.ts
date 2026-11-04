import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// Setup, analytics and portal pages are lazy-loaded chunks; the first import can take over the 1 s default
// when the whole suite runs in parallel.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => cleanup());
