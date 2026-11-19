const demoRecords = [
  ["Alex Morgan", "Paul Weiss", "New York", "Corporate", "Mergers and Acquisitions"],
  ["Amelia Chen", "Simpson Thacher", "London", "Mergers and Acquisitions"],
  ["Daniel Foster", "Paul Weiss", "London", "Corporate"],
  ["Eleanor Brooks", "Simpson Thacher", "New York", "Corporate"],
  ["Hannah Reyes", "Paul Weiss", "Washington, DC", "Mergers and Acquisitions"],
  ["James Okafor", "Simpson Thacher", "London", "Corporate", "Mergers and Acquisitions"],
  ["Maya Bennett", "Paul Weiss", "New York", "Corporate"],
  ["Nathan Patel", "Simpson Thacher", "Palo Alto", "Mergers and Acquisitions"],
  ["Olivia Clarke", "Paul Weiss", "London", "Mergers and Acquisitions"],
  ["Samuel Kim", "Simpson Thacher", "Palo Alto", "Corporate"],
  ["Sofia Ellis", "Paul Weiss", "Washington, DC", "Corporate"],
  ["Zara Mitchell", "Simpson Thacher", "New York", "Mergers and Acquisitions"],
].map(([name, firm_name, office, ...practices], index) => ({
  partner_entry_id: `demo-${index + 1}`,
  name,
  firm_name,
  firm_key: firm_name.toLowerCase().replaceAll(" ", "_"),
  role: "Partner",
  offices: [office],
  practices,
}));

export function createDirectoryApi(baseUrl) {
  const base = baseUrl.trim().replace(/\/+$/, "");

  async function request(path, allowMissing = false) {
    const response = await fetch(`${base}${path}`, {
      headers: { Accept: "application/json" },
    });
    if (allowMissing && response.status === 404) return null;
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return response.json();
  }

  return {
    demo: !base,
    async list() {
      if (!base) {
        return {
          records: demoRecords,
        };
      }
      const data = await request("/partners");
      if (!Array.isArray(data?.records)) throw new Error("Invalid roster response");
      return data;
    },
    async profile(id) {
      if (!base) return null;
      return request(`/partners/${encodeURIComponent(id)}`, true);
    },
  };
}
