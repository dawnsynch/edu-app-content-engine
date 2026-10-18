import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiStatus } from "./api-status";

describe("ApiStatus", () => {
  it("renders online status when API health is ok", () => {
    render(
      <ApiStatus health={{ status: "ok", service: "edu-dawnsynch-api", environment: "test" }} />
    );

    expect(screen.getByText("Online")).toBeInTheDocument();
    expect(screen.getByText("edu-dawnsynch-api")).toBeInTheDocument();
  });
});

