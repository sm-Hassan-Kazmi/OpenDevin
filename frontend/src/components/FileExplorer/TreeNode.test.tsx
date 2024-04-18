import React from "react";
import { act, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TreeNode from "./TreeNode";

const onFileClick = vi.fn();

const NODE: TreeNode = {
  name: "folder",
  children: [
    { name: "file.ts" },
    { name: "folder2", children: [{ name: "file2.ts" }] },
  ],
};

describe("TreeNode", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("should render a file if property has no children", () => {
    const { getByText } = render(
      <TreeNode node={NODE} path={NODE.name} onFileClick={onFileClick} />,
    );
    expect(getByText("file.ts")).toBeInTheDocument();
  });

  it("should render a folder if property has children", () => {
    const { getByText } = render(
      <TreeNode node={NODE} path={NODE.name} onFileClick={onFileClick} />,
    );
    expect(getByText("folder")).toBeInTheDocument();
    expect(getByText("file.ts")).toBeInTheDocument();
  });

  it("should close a folder when clicking on it", () => {
    const { getByText, queryByText } = render(
      <TreeNode node={NODE} path={NODE.name} onFileClick={onFileClick} />,
    );

    act(() => {
      userEvent.click(getByText("folder2"));
    });

    expect(queryByText("file2.ts")).not.toBeInTheDocument();
    expect(getByText("folder")).toBeInTheDocument();
    expect(getByText("file.ts")).toBeInTheDocument();
  });

  it("should open a folder when clicking on it", () => {
    const { getByText, queryByText } = render(
      <TreeNode node={NODE} path={NODE.name} onFileClick={onFileClick} />,
    );

    act(() => {
      userEvent.click(getByText("folder"));
    });

    expect(queryByText("folder2")).not.toBeInTheDocument();
    expect(queryByText("file2.ts")).not.toBeInTheDocument();
    expect(queryByText("file.ts")).not.toBeInTheDocument();

    act(() => {
      userEvent.click(getByText("folder"));
    });

    expect(getByText("folder2")).toBeInTheDocument();
    expect(getByText("file2.ts")).toBeInTheDocument();
    expect(getByText("file.ts")).toBeInTheDocument();
  });

  it("should return the full path of a file when clicking on it", () => {
    const { getByText } = render(
      <TreeNode node={NODE} path={NODE.name} onFileClick={onFileClick} />,
    );

    act(() => {
      userEvent.click(getByText("file.ts"));
    });

    expect(onFileClick).toHaveBeenCalledWith("folder/file.ts");

    act(() => {
      userEvent.click(getByText("file2.ts"));
    });

    expect(onFileClick).toHaveBeenCalledWith("folder/folder2/file2.ts");
  });

  it("should render the explorer given the defaultExpanded prop", () => {
    const { getByText, queryByText } = render(
      <TreeNode
        node={NODE}
        path={NODE.name}
        onFileClick={onFileClick}
        defaultOpen={false}
      />,
    );

    expect(getByText("folder")).toBeInTheDocument();
    expect(queryByText("folder2")).not.toBeInTheDocument();
    expect(queryByText("file2.ts")).not.toBeInTheDocument();
    expect(queryByText("file.ts")).not.toBeInTheDocument();

    act(() => {
      userEvent.click(getByText("folder"));
    });

    expect(getByText("folder2")).toBeInTheDocument();
    expect(getByText("file2.ts")).toBeInTheDocument();
    expect(getByText("file.ts")).toBeInTheDocument();
  });

  it.todo(
    "should maintain the expanded state of child folders when closing and opening a parent folder",
  );
});
