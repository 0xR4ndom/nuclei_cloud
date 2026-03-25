"use client";

import { useEffect, useState, useRef } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { targetsApi } from "@/lib/api";
import type { TargetList } from "@/types";
import { Plus, Trash2, Upload, FolderOpen } from "lucide-react";
import toast from "react-hot-toast";

export default function TargetsPage() {
  const [lists, setLists] = useState<TargetList[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [rawTargets, setRawTargets] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function fetchLists() {
    setLoading(true);
    try {
      const res = await targetsApi.lists();
      setLists(res.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLists();
  }, []);

  async function handleCreateList() {
    if (!newListName.trim()) return toast.error("Name required");
    try {
      await targetsApi.createList({ name: newListName });
      toast.success("List created");
      setNewListName("");
      setShowCreate(false);
      fetchLists();
    } catch {
      toast.error("Failed to create list");
    }
  }

  async function handleImport(listId: string) {
    const lines = rawTargets
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!lines.length) return toast.error("No targets provided");
    try {
      const res = await targetsApi.importBulk({
        targets: lines,
        target_list_id: listId,
      });
      toast.success(
        `Imported ${res.data.created} targets (${res.data.skipped} duplicates)`
      );
      setRawTargets("");
      fetchLists();
    } catch {
      toast.error("Import failed");
    }
  }

  async function handleFileUpload(
    e: React.ChangeEvent<HTMLInputElement>,
    listId: string
  ) {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(
        `/api/v1/targets/upload?target_list_id=${listId}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${document.cookie
              .split("; ")
              .find((r) => r.startsWith("access_token="))
              ?.split("=")[1]}`,
          },
          body: formData,
        }
      );
      const data = await res.json();
      toast.success(`Imported ${data.created} targets`);
      fetchLists();
    } catch {
      toast.error("Upload failed");
    }
  }

  async function handleDeleteList(id: string) {
    if (!confirm("Delete this target list?")) return;
    try {
      await targetsApi.deleteList(id);
      toast.success("Deleted");
      setLists((prev) => prev.filter((l) => l.id !== id));
    } catch {
      toast.error("Failed to delete");
    }
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Targets</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Manage target lists for scanning
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New List
          </button>
        </div>

        {/* Create list modal */}
        {showCreate && (
          <div className="rounded-xl border border-border bg-card p-5 space-y-3">
            <h2 className="text-sm font-semibold text-foreground">
              Create Target List
            </h2>
            <input
              type="text"
              value={newListName}
              onChange={(e) => setNewListName(e.target.value)}
              placeholder="List name"
              className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreateList}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Create
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 rounded-lg bg-secondary text-muted-foreground text-sm hover:text-foreground transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Lists */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : lists.length === 0 ? (
          <div className="rounded-xl border border-border bg-card py-16 text-center text-muted-foreground text-sm">
            No target lists yet
          </div>
        ) : (
          <div className="space-y-4">
            {lists.map((list) => (
              <div
                key={list.id}
                className="rounded-xl border border-border bg-card p-5 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FolderOpen className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">
                        {list.name}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {list.target_count} targets
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteList(list.id)}
                    className="p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {/* Import area */}
                <div className="space-y-2">
                  <textarea
                    placeholder="Paste targets (one per line)&#10;https://example.com&#10;192.168.1.0/24"
                    value={rawTargets}
                    onChange={(e) => setRawTargets(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-xs font-mono resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleImport(list.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary text-sm text-foreground hover:bg-secondary/70 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Import
                    </button>
                    <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary text-sm text-foreground hover:bg-secondary/70 transition-colors cursor-pointer">
                      <Upload className="w-3.5 h-3.5" />
                      Upload File
                      <input
                        ref={fileRef}
                        type="file"
                        accept=".txt,.csv"
                        className="hidden"
                        onChange={(e) => handleFileUpload(e, list.id)}
                      />
                    </label>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
