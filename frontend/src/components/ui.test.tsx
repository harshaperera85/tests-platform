import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Alert, Button, Pill } from "./ui";

describe("ui primitives", () => {
  it("Button defaults to type=button and fires onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    const btn = screen.getByRole("button", { name: "Go" });
    expect(btn).toHaveAttribute("type", "button");
    btn.click();
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("Pill renders its content", () => {
    render(<Pill tone="ok">ready</Pill>);
    expect(screen.getByText("ready")).toBeInTheDocument();
  });

  it("Alert exposes role=alert with title + body", () => {
    render(<Alert tone="warn" title="Heads up">details</Alert>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Heads up");
    expect(alert).toHaveTextContent("details");
  });
});
