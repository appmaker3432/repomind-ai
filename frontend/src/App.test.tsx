import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("RepoMind dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("rejects malformed repository URLs before issuing a request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<App />);
    fireEvent.change(screen.getByLabelText("PUBLIC REPOSITORY URL"), {
      target: { value: "https://github.com.evil.example/owner/repo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /analyze repository/i }));
    expect(screen.getByRole("alert")).toHaveTextContent("public GitHub URL");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it.each([
    ["openai", "OpenAI API"],
    ["gemini", "Google Gemini API"],
  ])("requires explicit consent before %s analysis", (provider, providerLabel) => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<App />);
    fireEvent.change(screen.getByLabelText("PUBLIC REPOSITORY URL"), {
      target: { value: "https://github.com/owner/repo" },
    });
    fireEvent.change(screen.getByLabelText("AI ANALYSIS"), { target: { value: provider } });
    fireEvent.click(screen.getByRole("button", { name: /analyze repository/i }));
    expect(screen.getByRole("alert")).toHaveTextContent("explicit consent");
    expect(fetchSpy).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("AI ANALYSIS"), { target: { value: provider } });
    expect(screen.getByRole("checkbox")).toHaveAccessibleName(new RegExp(providerLabel));
  });
});
