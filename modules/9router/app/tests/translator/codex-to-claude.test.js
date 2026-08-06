import { describe, expect, it } from "vitest";
import "./registerAll.js";
import { translateResponse, initState } from "../../open-sse/translator/index.js";
import { FORMATS } from "../../open-sse/translator/formats.js";

describe("OpenAI Responses to Claude streaming", () => {
  it("emits a complete Anthropic text stream", () => {
    const state = initState(FORMATS.CLAUDE);
    const events = [
      { type: "response.created", response: { id: "resp_1", model: "gpt-5.5" } },
      { type: "response.output_text.delta", delta: "Hello" },
      { type: "response.completed", response: { usage: { input_tokens: 10, output_tokens: 5 } } },
    ];
    const output = events.flatMap((event) => translateResponse(FORMATS.OPENAI_RESPONSES, FORMATS.CLAUDE, event, state));
    expect(output.map((item) => item.type)).toEqual([
      "message_start",
      "content_block_start",
      "content_block_delta",
      "content_block_stop",
      "message_delta",
      "message_stop",
    ]);
    expect(output.find((item) => item.type === "content_block_delta")?.delta?.text).toBe("Hello");
  });
});
