import { createDirectoryApi } from "./api.js";

const byId = (id) => document.getElementById(id);
const api = createDirectoryApi(document.querySelector('meta[name="api-base"]').content);
const storageKey = api.demo ? "pinpoint-demo-saved" : "pinpoint-saved";
const pageSize = 8;
const collator = new Intl.Collator("en", { sensitivity: "base" });
const filters = {
  firm: byId("firm"),
  office: byId("office"),
  practice: byId("practice"),
};
const state = { records: [], saved: readSaved(), savedOnly: false, page: 1 };
const dialog = byId("profile");
let profileRequest = 0;

function readSaved() {
  try {
    const ids = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    return new Set(Array.isArray(ids) ? ids : []);
  } catch {
    return new Set();
  }
}

function element(tag, content = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = content;
  if (className) node.className = className;
  return node;
}

function setOptions(select, values) {
  for (const value of [...new Set(values)].filter(Boolean).sort(collator.compare)) {
    select.append(new Option(value, value));
  }
}

function render() {
  const query = byId("search").value.trim().toLocaleLowerCase();
  const matches = state.records.filter((record) => {
    const searchable = [record.name, record.firm_name, ...record.offices, ...record.practices];
    return (!state.savedOnly || state.saved.has(record.partner_entry_id))
      && (!filters.firm.value || record.firm_name === filters.firm.value)
      && (!filters.office.value || record.offices.includes(filters.office.value))
      && (!filters.practice.value || record.practices.includes(filters.practice.value))
      && searchable.some((value) => value.toLocaleLowerCase().includes(query));
  });
  const direction = byId("sort").value === "asc" ? 1 : -1;
  matches.sort((a, b) => direction * collator.compare(a.name, b.name));
  const pageCount = Math.max(1, Math.ceil(matches.length / pageSize));
  state.page = Math.min(state.page, pageCount);
  const start = (state.page - 1) * pageSize;
  const visible = matches.slice(start, start + pageSize);
  const savedCount = state.records.filter((record) => state.saved.has(record.partner_entry_id)).length;

  byId("results-title").textContent = state.savedOnly ? "Saved partners" : "All partners";
  byId("saved-count").textContent = savedCount;
  byId("result-status").textContent = `${matches.length} ${matches.length === 1 ? "partner" : "partners"}`;
  byId("table-wrap").hidden = !matches.length;
  byId("rows").replaceChildren(...visible.map(renderRow));
  byId("pagination").hidden = !matches.length;
  byId("range").textContent = `Showing ${start + 1}–${start + visible.length} of ${matches.length}`;
  byId("previous").disabled = state.page === 1;
  byId("next").disabled = state.page >= pageCount;
  byId("empty").hidden = Boolean(matches.length);
  byId("empty").textContent = !state.records.length
    ? "No enriched partner profiles are available yet."
    : state.savedOnly && !savedCount
    ? "Save a partner from the directory to find them here."
    : "No partners match your search and filters.";
}

function renderRow(record) {
  const row = element("tr");
  const personCell = element("td");
  const person = element("div", "", "person");
  const initials = record.name.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("");
  const avatar = element("span", initials, "initials");
  avatar.setAttribute("aria-hidden", "true");
  const name = element("button", record.name, "name");
  name.addEventListener("click", () => openProfile(record));
  const identity = element("div");
  identity.append(name, element("span", record.role, "role"));
  person.append(avatar, identity);
  personCell.append(person);

  const practiceCell = element("td");
  const tags = element("div", "", "tags");
  for (const practice of record.practices) tags.append(element("span", practice, "tag"));
  practiceCell.append(tags);
  const bookmarkCell = element("td");
  const bookmark = element("button", "", "save");
  bookmark.append(byId("bookmark-icon").content.cloneNode(true));
  updateBookmark(bookmark, record);
  bookmark.addEventListener("click", () => {
    const id = record.partner_entry_id;
    if (state.saved.has(id)) state.saved.delete(id);
    else state.saved.add(id);
    try {
      localStorage.setItem(storageKey, JSON.stringify([...state.saved]));
    } catch {
      // Keep the selection for this session when browser storage is unavailable.
    }
    if (state.savedOnly) {
      render();
      byId("saved-tab").focus();
    } else {
      updateBookmark(bookmark, record);
      byId("saved-count").textContent = state.records.filter(
        (item) => state.saved.has(item.partner_entry_id)
      ).length;
    }
  });
  bookmarkCell.append(bookmark);
  const firmCell = element("td", record.firm_name);
  if (record.scope_verified === false) {
    firmCell.append(element("span", "Partial coverage", "role"));
  }
  row.append(personCell, firmCell, element("td", record.offices.join(", ") || "—"), practiceCell, bookmarkCell);
  return row;
}

function updateBookmark(button, record) {
  const saved = state.saved.has(record.partner_entry_id);
  button.setAttribute("aria-pressed", String(saved));
  button.setAttribute("aria-label", `${saved ? "Remove saved partner" : "Save partner"}: ${record.name}`);
}

function sourceLink(value, label = "View firm profile") {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    const link = element("a", label);
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  } catch {
    return null;
  }
}

function profileResearch(record) {
  const section = element("section", "", "profile-research");
  section.append(element("h3", "Live web research"));
  const form = element("form");
  form.action = "https://www.google.com/search";
  form.target = "_blank";
  form.rel = "noopener noreferrer";
  const label = element("label", "Google search query");
  const input = element("input");
  input.type = "search";
  input.name = "q";
  input.required = true;
  const partnerQuery = `"${record.name}" "${record.firm_name}"`;
  input.value = api.demo ? "" : partnerQuery;
  if (api.demo) input.placeholder = "Enter a real partner’s name and firm";
  label.append(input);
  const topics = element("div", "", "research-topics");
  for (const [name, terms] of [
    ["Recent deals", "M&A deals"],
    ["Press coverage", "news"],
    ["Firm announcements", "partner announcement"],
  ]) {
    const button = element("button", name, "clear");
    button.type = "button";
    button.addEventListener("click", () => { input.value = `${partnerQuery} ${terms}`; });
    topics.append(button);
  }
  form.append(label);
  if (!api.demo) form.append(topics);
  form.append(element("button", "Search Google (opens a new tab)", "research-submit"));
  section.append(form);
  return section;
}

async function openProfile(record) {
  const request = ++profileRequest;
  const content = byId("profile-content");
  const title = element("h2", record.name);
  title.id = "profile-title";
  const overview = element("dl");
  for (const [label, value] of [
    ["Firm", record.firm_name],
    ["Office", record.offices.join(", ")],
    ["Practice", record.practices.join(", ")],
  ]) {
    if (value) overview.append(element("dt", label), element("dd", value));
  }
  const status = element("p", api.demo ? "Sample record for the directory preview." : "Loading profile details…");
  status.setAttribute("role", "status");
  content.replaceChildren(title, element("p", record.role), overview);
  const link = sourceLink(record.profile_url);
  if (link) content.append(link);
  content.append(profileResearch(record), status);
  dialog.showModal();
  if (api.demo) return;

  try {
    const profile = await api.profile(record.partner_entry_id);
    if (request !== profileRequest || !dialog.open) return;
    if (!profile) {
      status.textContent = "Profile enrichment is unavailable for this partner.";
      return;
    }
    status.remove();
    for (const [label, value] of [
      ["Biography", profile.biography],
      ["Email", profile.email],
      ["Telephone", profile.phone_numbers],
      ["Education", profile.education],
      ["Admissions", profile.admissions],
      ["Languages", profile.languages],
    ]) {
      const text = Array.isArray(value) ? value.join("\n") : value;
      if (text) content.append(element("h3", label), element("p", text));
    }
    const checked = new Date(profile.source_checked_at ?? "");
    if (Number.isFinite(checked.getTime())) {
      content.append(element("p", `Source checked ${checked.toLocaleDateString("en-GB")}`));
    }
  } catch {
    if (request === profileRequest && dialog.open) status.textContent = "Profile details could not be loaded.";
  }
}

function resetPage() {
  state.page = 1;
  render();
}

function showSaved(savedOnly) {
  state.savedOnly = savedOnly;
  showView(savedOnly ? "saved-tab" : "directory-tab");
  byId("filters").reset();
}

function showView(activeTab) {
  for (const id of ["directory-tab", "saved-tab", "changes-tab"]) {
    if (id === activeTab) byId(id).setAttribute("aria-current", "page");
    else byId(id).removeAttribute("aria-current");
  }
  const changes = activeTab === "changes-tab";
  byId("directory").hidden = changes;
  byId("recent-changes").hidden = !changes;
}

const sampleChanges = [
  { name: "Alex Morgan", firm_name: "Example Firm A", kind: "newly_listed", observed_at: "2026-11-19" },
  { name: "Robin Ellis", firm_name: "Example Firm B", kind: "no_longer_listed", observed_at: "2026-11-18" },
  { name: "Sam Chen", firm_name: "Example Firm B", kind: "newly_listed", observed_at: "2026-11-17" },
];

function changeRows(changes) {
  const labels = new Map([
    ["newly_listed", "Newly listed"],
    ["no_longer_listed", "No longer listed"],
    ["relisted", "Listed again"],
  ]);
  return changes
    .filter((change) => labels.has(change.kind))
    .sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at))
    .map((change) => {
      const row = element("li");
      const date = new Date(change.observed_at);
      const observed = Number.isFinite(date.getTime())
        ? date.toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: "UTC" })
        : "Date unavailable";
      row.append(
        element("strong", change.name),
        element("span", `${change.firm_name} · ${labels.get(change.kind)} · ${observed}`),
      );
      const source = sourceLink(change.source_url, "View roster source");
      if (source) row.append(source);
      return row;
    });
}

function renderMoves(moves = []) {
  const rows = moves.map((move) => {
    const row = element("li");
    const observed = new Date(move.observed_at).toLocaleDateString("en-GB", {
      dateStyle: "medium", timeZone: "UTC",
    });
    const status = move.status === "confirmed" ? "Confirmed move" : "Possible move";
    row.append(
      element("strong", move.name),
      element("span", `${move.from_firm} → ${move.to_firm} · ${status}`),
      element("span", `Observed ${observed}`),
    );
    if (move.effective_on) {
      const effective = new Date(move.effective_on).toLocaleDateString("en-GB", {
        dateStyle: "medium", timeZone: "UTC",
      });
      row.append(element("span", `Effective ${effective}`));
    }
    for (const [url, label] of [
      [move.evidence_url, "View confirmation source"],
      [move.from_source_url, "View previous firm source"],
      [move.to_source_url, "View destination firm profile"],
    ]) {
      const link = sourceLink(url, label);
      if (link) row.append(link);
    }
    return row;
  });
  byId("partner-moves-list").replaceChildren(...rows);
  byId("partner-moves").hidden = api.demo;
  byId("partner-moves-empty").hidden = rows.length > 0;
}

function renderChanges(changes, moves) {
  renderMoves(moves);
  const liveRows = changeRows(Array.isArray(changes) ? changes : []);
  byId("changes-list").replaceChildren(...liveRows);
  byId("sample-changes-list").replaceChildren(...changeRows(sampleChanges));
  byId("sample-changes").open = liveRows.length === 0;
  byId("changes-status").textContent = api.demo
    ? ""
    : !Array.isArray(changes) ? "Roster change history is unavailable."
    : liveRows.length ? "" : "No roster changes reported.";
}

async function start() {
  try {
    const { records, changes, coverage, moves } = await api.list();
    state.records = records;
    renderChanges(changes, moves);
    setOptions(filters.firm, state.records.map((record) => record.firm_name));
    setOptions(filters.office, state.records.flatMap((record) => record.offices));
    setOptions(filters.practice, state.records.flatMap((record) => record.practices));
    if (api.demo) {
      byId("data-status").textContent = "Demo data · Sample records";
      byId("data-status").hidden = false;
    } else if (coverage?.verified_firm_count != null && coverage?.target_firm_count != null) {
      const partial = coverage.partial_firm_count > 0
        ? ` · ${coverage.partial_firm_count} with partial coverage`
        : "";
      byId("data-status").textContent = `Verified coverage: ${coverage.verified_firm_count} of ${coverage.target_firm_count} firms${partial}`;
      byId("data-status").hidden = false;
    }
    render();
  } catch {
    byId("result-status").textContent = "Directory unavailable";
    const retry = element("button", "Retry", "clear");
    retry.addEventListener("click", () => {
      retry.disabled = true;
      start();
    });
    byId("empty").replaceChildren(element("p", "The partner directory could not be loaded."), retry);
    byId("empty").hidden = false;
    return;
  }
  byId("filters").addEventListener("submit", (event) => event.preventDefault());
  byId("filters").addEventListener("reset", () => setTimeout(resetPage, 0));
  byId("search").addEventListener("input", resetPage);
  for (const select of [...Object.values(filters), byId("sort")]) {
    select.addEventListener("change", resetPage);
  }
  byId("directory-tab").addEventListener("click", () => showSaved(false));
  byId("saved-tab").addEventListener("click", () => showSaved(true));
  byId("changes-tab").addEventListener("click", () => {
    showView("changes-tab");
    byId("changes-title").focus();
  });
  byId("previous").addEventListener("click", () => { state.page--; render(); });
  byId("next").addEventListener("click", () => { state.page++; render(); });
}

start();
