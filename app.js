const statusLabels = {
  uncontacted: "Uncontacted",
  contacted: "Contacted",
  joined: "Joined",
  not_fit: "Not a fit",
};

const statusOrder = ["uncontacted", "contacted", "joined", "not_fit"];
const stateKey = "creatorState.v1";

const searchInput = document.getElementById("search");
const filterSelect = document.getElementById("filter");
const sortSelect = document.getElementById("sort");
const listEl = document.getElementById("creator-list");
const metaCount = document.getElementById("meta-count");
const errorEl = document.getElementById("error");
const exportBtn = document.getElementById("export");
const resetBtn = document.getElementById("reset");
const loadBtn = document.getElementById("load");

const statEls = {
  total: document.getElementById("stat-total"),
  uncontacted: document.getElementById("stat-uncontacted"),
  contacted: document.getElementById("stat-contacted"),
  joined: document.getElementById("stat-joined"),
};

let creators = [];
let creatorState = loadState();

function loadState() {
  try {
    return JSON.parse(localStorage.getItem(stateKey)) || {};
  } catch (error) {
    return {};
  }
}

function saveState() {
  localStorage.setItem(stateKey, JSON.stringify(creatorState));
}

function getMeta(handle) {
  return creatorState[handle] || {
    status: "uncontacted",
    note: "",
    updatedAt: 0,
  };
}

function updateMeta(handle, updates) {
  const current = getMeta(handle);
  creatorState[handle] = {
    ...current,
    ...updates,
    updatedAt: Date.now(),
  };
  saveState();
}

function parseStreamers(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((handle) => ({
      handle,
      profileUrl: `https://www.tiktok.com/@${handle}`,
    }));
}

function render() {
  const query = searchInput.value.trim().toLowerCase();
  const filter = filterSelect.value;
  const sort = sortSelect.value;

  let filtered = creators.filter((creator) => {
    const meta = getMeta(creator.handle);
    const matchesQuery = creator.handle.toLowerCase().includes(query);
    const matchesFilter = filter === "all" || meta.status === filter;
    return matchesQuery && matchesFilter;
  });

  if (sort === "alpha") {
    filtered = filtered.sort((a, b) => a.handle.localeCompare(b.handle));
  } else if (sort === "alpha_desc") {
    filtered = filtered.sort((a, b) => b.handle.localeCompare(a.handle));
  } else if (sort === "updated") {
    filtered = filtered.sort((a, b) => {
      const aMeta = getMeta(a.handle).updatedAt || 0;
      const bMeta = getMeta(b.handle).updatedAt || 0;
      return bMeta - aMeta;
    });
  }

  listEl.innerHTML = filtered
    .map((creator, index) => {
      const meta = getMeta(creator.handle);
      const updated = meta.updatedAt
        ? new Date(meta.updatedAt).toLocaleString()
        : "Never updated";
      return `
      <article class="creator-card" style="--index: ${index}">
        <div class="creator-header">
          <div>
            <div class="creator-handle">@${creator.handle}</div>
            <a class="link" href="${creator.profileUrl}" target="_blank" rel="noreferrer">
              View profile
            </a>
          </div>
          <span class="chip">${statusLabels[meta.status]}</span>
        </div>
        <div class="creator-actions">
          <button class="button ghost copy" data-handle="${creator.handle}">Copy</button>
          <select data-handle="${creator.handle}" class="status-select">
            ${statusOrder
              .map(
                (status) => `
              <option value="${status}" ${
                  status === meta.status ? "selected" : ""
                }>${statusLabels[status]}</option>
            `
              )
              .join("")}
          </select>
        </div>
        <textarea
          class="note"
          data-handle="${creator.handle}"
          placeholder="Add notes or follow-up context..."
        >${meta.note || ""}</textarea>
        <div class="card-footer">
          <span>Last updated: ${updated}</span>
        </div>
      </article>
    `;
    })
    .join("");

  updateStats();
  metaCount.textContent = `${filtered.length} creators`;
}

function updateStats() {
  const totals = {
    total: creators.length,
    uncontacted: 0,
    contacted: 0,
    joined: 0,
    not_fit: 0,
  };

  creators.forEach((creator) => {
    const status = getMeta(creator.handle).status;
    totals[status] += 1;
  });

  statEls.total.textContent = totals.total;
  statEls.uncontacted.textContent = totals.uncontacted;
  statEls.contacted.textContent = totals.contacted;
  statEls.joined.textContent = totals.joined;
}

async function loadData() {
  try {
    const response = await fetch("active_streamers.txt", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Failed to fetch active_streamers.txt");
    }
    const text = await response.text();
    creators = parseStreamers(text);
    errorEl.classList.add("hidden");
    render();
  } catch (error) {
    errorEl.classList.remove("hidden");
  }
}

function exportCsv() {
  const rows = [["handle", "status", "note", "updated_at"]];
  creators.forEach((creator) => {
    const meta = getMeta(creator.handle);
    rows.push([
      creator.handle,
      meta.status,
      meta.note || "",
      meta.updatedAt ? new Date(meta.updatedAt).toISOString() : "",
    ]);
  });
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "creator_export.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function resetState() {
  if (!confirm("Clear all local notes and statuses?")) {
    return;
  }
  creatorState = {};
  saveState();
  render();
}

listEl.addEventListener("change", (event) => {
  const target = event.target;
  if (target.classList.contains("status-select")) {
    updateMeta(target.dataset.handle, { status: target.value });
    render();
  }
});

listEl.addEventListener("input", (event) => {
  const target = event.target;
  if (target.classList.contains("note")) {
    updateMeta(target.dataset.handle, { note: target.value });
  }
});

listEl.addEventListener("click", async (event) => {
  const target = event.target;
  if (target.classList.contains("copy")) {
    const handle = target.dataset.handle;
    try {
      await navigator.clipboard.writeText(handle);
      target.textContent = "Copied";
      setTimeout(() => {
        target.textContent = "Copy";
      }, 1200);
    } catch (error) {
      target.textContent = "Failed";
      setTimeout(() => {
        target.textContent = "Copy";
      }, 1200);
    }
  }
});

searchInput.addEventListener("input", render);
filterSelect.addEventListener("change", render);
sortSelect.addEventListener("change", render);
exportBtn.addEventListener("click", exportCsv);
resetBtn.addEventListener("click", resetState);

loadBtn.addEventListener("click", loadData);
