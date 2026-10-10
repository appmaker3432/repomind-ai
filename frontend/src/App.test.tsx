import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    fireEvent.change(screen.getByLabelText(provider === "gemini" ? "YOUR GOOGLE GEMINI API KEY" : "YOUR OPENAI API KEY"), {
      target: { value: "test-user-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: /analyze repository/i }));
    expect(screen.getByRole("alert")).toHaveTextContent("explicit consent");
    expect(fetchSpy).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("AI ANALYSIS"), { target: { value: provider } });
    expect(screen.getByRole("checkbox")).toHaveAccessibleName(new RegExp(providerLabel));
  });

  it("sends the supplied key for one analysis and clears it afterward", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Provider request failed." }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(<App />);
    fireEvent.change(screen.getByLabelText("PUBLIC REPOSITORY URL"), {
      target: { value: "https://github.com/owner/repo" },
    });
    fireEvent.change(screen.getByLabelText("AI ANALYSIS"), { target: { value: "openai" } });
    const keyInput = screen.getByLabelText("YOUR OPENAI API KEY");
    fireEvent.change(keyInput, { target: { value: "user-secret-key" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /analyze repository/i }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalledOnce());
    const request = JSON.parse(fetchSpy.mock.calls[0][1]?.body as string);
    expect(request).toMatchObject({
      ai_provider: "openai",
      api_key: "user-secret-key",
      ai_model: "gpt-4o-mini",
      consent_to_send_source: true,
    });
    await waitFor(() => expect(keyInput).toHaveValue(""));
    expect(window.localStorage.length).toBe(0);
  });
});
