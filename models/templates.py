html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeChef Stats API Documentation</title>
    <style>
        :root {
            --primary-color: #f59e0b;
            --secondary-color: #fbbf24;
            --background-color: #0b1120;
            --card-background: #111827;
            --code-background: #0f172a;
            --text-color: #94a3b8;
            --heading-color: #f8fafc;
            --hover-color: #1f2937;
            --border-color: #243041;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 3rem 1.25rem 4rem;
            font-family: "SF Mono", "Fira Code", Monaco, monospace;
            line-height: 1.6;
            color: var(--text-color);
            background: var(--background-color);
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
        }

        h1, h2, h3 {
            color: var(--heading-color);
        }

        h1 {
            font-size: clamp(2rem, 4vw, 2.8rem);
            margin: 0 0 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--primary-color);
        }

        p {
            margin: 0.75rem 0;
        }

        .top-links {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin: 1.5rem 0 2rem;
        }

        .top-links a,
        .try-button {
            display: inline-block;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 700;
            transition: 0.2s ease;
        }

        .top-links a {
            color: var(--heading-color);
            background: var(--hover-color);
            border: 1px solid var(--border-color);
        }

        .top-links a:hover,
        .try-button:hover {
            transform: translateY(-1px);
        }

        .endpoint {
            margin: 1.25rem 0;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            background: var(--card-background);
            box-shadow: 0 10px 30px -15px rgba(2, 12, 27, 0.7);
        }

        .endpoint-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            padding: 1.25rem 1.5rem;
            cursor: pointer;
            background: var(--card-background);
        }

        .endpoint-header:hover {
            background: var(--hover-color);
        }

        .endpoint-header h2 {
            margin: 0;
            font-size: 1.1rem;
        }

        .endpoint-content {
            max-height: 0;
            overflow: hidden;
            padding: 0 1.5rem;
            transition: max-height 0.25s ease;
        }

        .endpoint.active .endpoint-content {
            max-height: 1200px;
            padding: 0 1.5rem 1.5rem;
        }

        .endpoint-toggle {
            color: var(--secondary-color);
            font-size: 1.4rem;
            font-weight: 700;
            transition: transform 0.2s ease;
        }

        .endpoint.active .endpoint-toggle {
            transform: rotate(45deg);
        }

        .endpoint-method {
            display: inline-block;
            margin-right: 0.6rem;
            padding: 0.25rem 0.5rem;
            border-radius: 5px;
            background: var(--primary-color);
            color: #0b1120;
            font-weight: 700;
        }

        code {
            padding: 0.25rem 0.45rem;
            border-radius: 6px;
            background: var(--code-background);
            color: var(--secondary-color);
            word-break: break-word;
        }

        pre {
            margin: 1rem 0;
            padding: 1rem;
            overflow-x: auto;
            border-radius: 10px;
            border: 1px solid var(--border-color);
            background: var(--code-background);
        }

        pre code {
            padding: 0;
            background: transparent;
            color: #e2e8f0;
        }

        .parameter,
        .note {
            margin: 1rem 0;
            padding: 1rem;
            border-left: 4px solid var(--primary-color);
            border-radius: 0 8px 8px 0;
            background: var(--hover-color);
        }

        .try-button {
            margin-top: 0.5rem;
            background: var(--primary-color);
            color: #0b1120;
        }

        .swagger-link {
            position: fixed;
            top: 1rem;
            right: 1rem;
            padding: 0.6rem 0.9rem;
            border-radius: 8px;
            border: 1px solid var(--primary-color);
            background: var(--hover-color);
            color: var(--heading-color);
            text-decoration: none;
            font-weight: 700;
        }

        .swagger-link:hover {
            background: var(--primary-color);
            color: #0b1120;
        }

        footer {
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
            font-size: 0.95rem;
        }

        @media (max-width: 640px) {
            body {
                padding-top: 4.5rem;
            }

            .swagger-link {
                left: 1rem;
                right: 1rem;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <a class="swagger-link" href="/docs">Open Swagger Docs</a>

    <div class="container">
        <h1>CodeChef Stats API Documentation</h1>
        <p>
            FastAPI REST API for public CodeChef profile data. This API exposes separate endpoints
            for profile information, heatmap activity, and rating history.
        </p>
        <div class="note">
            Upstream CodeChef responses are cached in memory and API routes are rate-limited per client IP.
        </div>

        <div class="top-links">
            <a href="/dashboard">Dashboard</a>
            <a href="/profile/tourist">Profile Example</a>
            <a href="/heatmap/tourist">Heatmap Example</a>
            <a href="/rating/tourist">Rating Example</a>
        </div>

        <div class="endpoint active">
            <div class="endpoint-header">
                <h2><span class="endpoint-method">GET</span><code>/profile/{handle}</code></h2>
                <span class="endpoint-toggle">+</span>
            </div>
            <div class="endpoint-content">
                <p>Returns core profile information for a CodeChef user.</p>
                <div class="parameter"><code>handle</code> Required CodeChef username.</div>
                <pre><code>{
  "success": true,
  "status": 200,
  "handle": "tourist",
  "profile": {
    "profile": "https://...",
    "name": "tourist",
    "currentRating": 2500,
    "highestRating": 2700,
    "countryFlag": "https://...",
    "countryName": "Belarus",
    "globalRank": 12,
    "countryRank": 1,
    "stars": "7 stars"
  }
}</code></pre>
                <a class="try-button" href="/profile/tourist">Try endpoint</a>
            </div>
        </div>

        <div class="endpoint">
            <div class="endpoint-header">
                <h2><span class="endpoint-method">GET</span><code>/heatmap/{handle}</code></h2>
                <span class="endpoint-toggle">+</span>
            </div>
            <div class="endpoint-content">
                <p>Returns daily submission heatmap entries for the user.</p>
                <div class="parameter"><code>handle</code> Required CodeChef username.</div>
                <pre><code>{
  "success": true,
  "status": 200,
  "handle": "tourist",
  "heatMap": [
    {"date": "2024-01-01", "value": 2}
  ]
}</code></pre>
                <a class="try-button" href="/heatmap/tourist">Try endpoint</a>
            </div>
        </div>

        <div class="endpoint">
            <div class="endpoint-header">
                <h2><span class="endpoint-method">GET</span><code>/rating/{handle}</code></h2>
                <span class="endpoint-toggle">+</span>
            </div>
            <div class="endpoint-content">
                <p>Returns contest rating history data for the user.</p>
                <div class="parameter"><code>handle</code> Required CodeChef username.</div>
                <pre><code>{
  "success": true,
  "status": 200,
  "handle": "tourist",
  "ratingData": [
    {"name": "JAN24", "rating": 1900}
  ]
}</code></pre>
                <a class="try-button" href="/rating/tourist">Try endpoint</a>
            </div>
        </div>

        <footer>
            <p>Built with FastAPI and uv. Interactive schema is available at <a href="/docs">/docs</a>.</p>
        </footer>
    </div>

    <script>
        document.querySelectorAll('.endpoint-header').forEach((header) => {
            header.addEventListener('click', () => {
                header.parentElement.classList.toggle('active');
            });
        });
    </script>
</body>
</html>
"""


dashboard_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeChef API Dashboard</title>
    <style>
        :root {
            --bg: #0b1120;
            --panel: #111827;
            --panel-soft: #172033;
            --text: #e5edf9;
            --muted: #95a3b8;
            --line: #263246;
            --accent: #f59e0b;
            --accent-soft: #fbbf24;
            --good: #10b981;
            --bad: #f43f5e;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            min-height: 100vh;
            background:
                radial-gradient(circle at top left, rgba(245, 158, 11, 0.16), transparent 28%),
                radial-gradient(circle at top right, rgba(251, 191, 36, 0.12), transparent 22%),
                linear-gradient(180deg, #09101d 0%, var(--bg) 100%);
            color: var(--text);
            font-family: Georgia, "Times New Roman", serif;
        }

        .shell {
            max-width: 1280px;
            margin: 0 auto;
            padding: 32px 20px 56px;
        }

        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 28px;
        }

        .topbar a {
            color: var(--muted);
            text-decoration: none;
            font-family: "SF Mono", "Fira Code", Monaco, monospace;
            font-size: 0.95rem;
        }

        .topbar a:hover {
            color: var(--accent-soft);
        }

        .hero {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 24px;
            margin-bottom: 24px;
        }

        .hero-card,
        .panel {
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.98), rgba(12, 18, 31, 0.98));
            border: 1px solid var(--line);
            border-radius: 22px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.28);
        }

        .hero-card {
            padding: 28px;
        }

        .eyebrow {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(245, 158, 11, 0.12);
            color: var(--accent-soft);
            font-family: "SF Mono", "Fira Code", Monaco, monospace;
            font-size: 0.74rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        h1 {
            margin: 16px 0 12px;
            font-size: clamp(2.5rem, 5vw, 4.6rem);
            line-height: 0.94;
            letter-spacing: -0.04em;
        }

        .hero p,
        .panel p {
            margin: 0;
            color: var(--muted);
            line-height: 1.7;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin-top: 24px;
        }

        .stat {
            padding: 14px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .stat strong,
        .stat span,
        .input-wrap label,
        button,
        .chip,
        .meta,
        pre {
            font-family: "SF Mono", "Fira Code", Monaco, monospace;
        }

        .stat strong {
            display: block;
            color: var(--text);
            font-size: 1.45rem;
            margin-bottom: 4px;
        }

        .panel {
            padding: 24px;
        }

        .input-wrap label {
            display: block;
            margin-bottom: 10px;
            font-size: 0.85rem;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .controls {
            display: flex;
            gap: 12px;
        }

        input {
            width: 100%;
            padding: 14px 16px;
            border-radius: 14px;
            border: 1px solid var(--line);
            background: var(--panel-soft);
            color: var(--text);
            font-size: 1rem;
            outline: none;
        }

        input:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.12);
        }

        button {
            padding: 14px 18px;
            border: 0;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--accent), var(--accent-soft));
            color: #16120a;
            font-weight: 700;
            cursor: pointer;
        }

        button:disabled {
            opacity: 0.65;
            cursor: wait;
        }

        .chips {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 18px;
        }

        .chip {
            padding: 8px 12px;
            border-radius: 999px;
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.03);
            color: var(--muted);
            cursor: pointer;
        }

        .chip:hover {
            color: var(--accent-soft);
            border-color: rgba(245, 158, 11, 0.4);
        }

        .status {
            min-height: 24px;
            margin-top: 16px;
            color: var(--muted);
            font-family: "SF Mono", "Fira Code", Monaco, monospace;
            font-size: 0.92rem;
        }

        .status.error {
            color: var(--bad);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 18px;
        }

        .api-card {
            border-radius: 20px;
            border: 1px solid var(--line);
            background: linear-gradient(180deg, rgba(18, 26, 42, 0.96), rgba(10, 15, 26, 0.96));
            overflow: hidden;
        }

        .api-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 18px;
            border-bottom: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.02);
        }

        .api-head h2 {
            margin: 0;
            font-size: 1rem;
            font-weight: 700;
        }

        .meta {
            font-size: 0.8rem;
            color: var(--muted);
        }

        .ok,
        .fail {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 700;
        }

        .ok {
            background: rgba(16, 185, 129, 0.12);
            color: var(--good);
        }

        .fail {
            background: rgba(244, 63, 94, 0.12);
            color: var(--bad);
        }

        pre {
            margin: 0;
            min-height: 340px;
            max-height: 560px;
            overflow: auto;
            padding: 18px;
            background: #08101d;
            color: #dbe6f5;
            font-size: 0.84rem;
            line-height: 1.6;
        }

        @media (max-width: 1024px) {
            .hero,
            .grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 640px) {
            .shell {
                padding: 18px 14px 36px;
            }

            .controls,
            .stats {
                grid-template-columns: 1fr;
                display: grid;
            }

            .controls {
                gap: 10px;
            }

            button {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="shell">
        <div class="topbar">
            <a href="/">Back to docs</a>
            <a href="/docs">Swagger</a>
        </div>

        <section class="hero">
            <div class="hero-card">
                <span class="eyebrow">Live dashboard</span>
                <h1>Inspect every API response for a CodeChef handle.</h1>
                <p>
                    Enter a handle and this page will fetch the profile, heatmap, and rating history endpoints
                    and render the raw JSON side by side.
                </p>

                <div class="stats">
                    <div class="stat">
                        <strong>3</strong>
                        <span>REST endpoints</span>
                    </div>
                    <div class="stat">
                        <strong>1</strong>
                        <span>shared handle input</span>
                    </div>
                    <div class="stat">
                        <strong>JSON</strong>
                        <span>rendered live</span>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="input-wrap">
                    <label for="handle-input">CodeChef Handle</label>
                    <div class="controls">
                        <input id="handle-input" type="text" placeholder="one_deepak" value="one_deepak" autocomplete="off" />
                        <button id="load-button" type="button">Load</button>
                    </div>
                </div>

                <div class="chips">
                    <button class="chip" type="button" data-handle="one_deepak">one_deepak</button>
                    <button class="chip" type="button" data-handle="tourist">tourist</button>
                    <button class="chip" type="button" data-handle="snackdown">snackdown</button>
                </div>

                <div id="status" class="status">Ready to fetch.</div>
            </div>
        </section>

        <section class="grid">
            <article class="api-card">
                <div class="api-head">
                    <h2>/profile/{handle}</h2>
                    <span id="profile-badge" class="meta">waiting</span>
                </div>
                <pre id="profile-output">{}
</pre>
            </article>

            <article class="api-card">
                <div class="api-head">
                    <h2>/heatmap/{handle}</h2>
                    <span id="heatmap-badge" class="meta">waiting</span>
                </div>
                <pre id="heatmap-output">[]
</pre>
            </article>

            <article class="api-card">
                <div class="api-head">
                    <h2>/rating/{handle}</h2>
                    <span id="rating-badge" class="meta">waiting</span>
                </div>
                <pre id="rating-output">[]
</pre>
            </article>
        </section>
    </div>

    <script>
        const handleInput = document.getElementById("handle-input");
        const loadButton = document.getElementById("load-button");
        const statusNode = document.getElementById("status");

        const endpoints = {
            profile: {
                path: (handle) => `/profile/${encodeURIComponent(handle)}`,
                output: document.getElementById("profile-output"),
                badge: document.getElementById("profile-badge"),
            },
            heatmap: {
                path: (handle) => `/heatmap/${encodeURIComponent(handle)}`,
                output: document.getElementById("heatmap-output"),
                badge: document.getElementById("heatmap-badge"),
            },
            rating: {
                path: (handle) => `/rating/${encodeURIComponent(handle)}`,
                output: document.getElementById("rating-output"),
                badge: document.getElementById("rating-badge"),
            },
        };

        function setBadge(node, ok, text) {
            node.className = ok ? "ok" : "fail";
            node.textContent = text;
        }

        async function fetchEndpoint(key, handle) {
            const target = endpoints[key];
            target.output.textContent = "Loading...";
            target.badge.className = "meta";
            target.badge.textContent = "loading";

            try {
                const response = await fetch(target.path(handle));
                const data = await response.json();
                target.output.textContent = JSON.stringify(data, null, 2);
                setBadge(target.badge, response.ok, `${response.status} ${response.ok ? "ok" : "error"}`);
                return response.ok;
            } catch (error) {
                target.output.textContent = JSON.stringify({ error: String(error) }, null, 2);
                setBadge(target.badge, false, "request failed");
                return false;
            }
        }

        async function loadDashboard(handle) {
            const trimmed = handle.trim();
            if (!trimmed) {
                statusNode.textContent = "Enter a CodeChef handle first.";
                statusNode.className = "status error";
                return;
            }

            loadButton.disabled = true;
            statusNode.textContent = `Fetching API responses for ${trimmed}...`;
            statusNode.className = "status";

            const results = await Promise.all([
                fetchEndpoint("profile", trimmed),
                fetchEndpoint("heatmap", trimmed),
                fetchEndpoint("rating", trimmed),
            ]);

            const allOk = results.every(Boolean);
            statusNode.textContent = allOk
                ? `Loaded all responses for ${trimmed}.`
                : `Finished with one or more failed requests for ${trimmed}.`;
            statusNode.className = allOk ? "status" : "status error";
            loadButton.disabled = false;
        }

        loadButton.addEventListener("click", () => loadDashboard(handleInput.value));
        handleInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                loadDashboard(handleInput.value);
            }
        });

        document.querySelectorAll(".chip").forEach((button) => {
            button.addEventListener("click", () => {
                handleInput.value = button.dataset.handle;
                loadDashboard(button.dataset.handle);
            });
        });

        loadDashboard(handleInput.value);
    </script>
</body>
</html>
"""
