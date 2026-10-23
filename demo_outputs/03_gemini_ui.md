HTML<!DOCTYPE html>
<html lang="en" class="h-full antialiased">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PulseTask — Offline-First Kanban Workspace</title>

  <!-- Tailwind CSS via CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
          },
          boxShadow: {
            'card': '0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.06)',
            'card-hover': '0 10px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.06)',
          }
        }
      }
    };
  </script>

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

  <!-- Core Backend Logic Engine -->
  <script src="kanban_engine.js"></script>

  <style>
    /* Custom scrollbars for Kanban board and columns */
    ::-webkit-scrollbar {
      width: 6px;
      height: 8px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(148, 163, 184, 0.45);
      border-radius: 9999px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: rgba(100, 116, 139, 0.7);
    }

    /* Drag & Drop visual states */
    .task-card {
      transition: transform 0.16s cubic-bezier(0.16, 1, 0.3, 1),
                  box-shadow 0.16s cubic-bezier(0.16, 1, 0.3, 1),
                  opacity 0.15s ease,
                  border-color 0.15s ease;
    }
    .task-card.is-dragging {
      opacity: 0.4;
      transform: scale(0.97) rotate(1deg);
      box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.15);
    }
    .column-dropzone {
      transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .column-dropzone.drag-over {
      background-color: rgba(238, 242, 255, 0.85);
      border-color: #6366f1;
      box-shadow: inset 0 0 0 2px rgba(99, 102, 241, 0.25);
    }
    .drop-indicator {
      height: 3px;
      background: linear-gradient(90deg, #6366f1, #8b5cf6);
      border-radius: 9999px;
      margin: 4px 0;
      pointer-events: none;
      box-shadow: 0 0 8px rgba(99, 102, 241, 0.5);
    }
    .line-clamp-2 {
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  </style>
</head>

<body class="h-full flex flex-col bg-slate-100 text-slate-900 select-none overflow-hidden">

  <!-- ==================== TOP HEADER ==================== -->
  <header class="bg-white/90 backdrop-blur-md border-b border-slate-200/80 px-4 sm:px-6 py-3 shrink-0 z-20">
    <div class="max-w-[1800px] mx-auto flex flex-wrap items-center justify-between gap-3">
      
      <!-- Brand Logo + Active Board Title -->
      <div class="flex items-center gap-3 sm:gap-4">
        <div class="flex items-center gap-2.5">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-600 via-indigo-500 to-violet-600 flex items-center justify-center text-white shadow-sm shadow-indigo-500/30">
            <!-- Heroicon: Bolt / Pulse -->
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="font-bold text-lg tracking-tight bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent">PulseTask</span>
              <span class="hidden sm:inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-indigo-50 text-indigo-600 rounded border border-indigo-200/60">Offline-First</span>
            </div>
          </div>
        </div>

        <div class="h-6 w-[1px] bg-slate-200 hidden sm:block"></div>

        <!-- Board Name Display -->
        <div class="flex items-center gap-2 bg-slate-100/90 border border-slate-200/80 rounded-lg px-3 py-1.5">
          <svg class="w-4 h-4 text-indigo-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
          </svg>
          <h1 id="boardTitleDisplay" class="text-sm font-semibold text-slate-800 truncate max-w-[200px] sm:max-w-[300px]">
            PulseTask Launch
          </h1>
          <span id="totalTasksBadge" class="ml-1 text-xs font-medium text-slate-500 bg-white px-2 py-0.5 rounded-md border border-slate-200/70">
            0 tasks
          </span>
        </div>
      </div>

      <!-- Quick Action Buttons -->
      <div class="flex items-center gap-2 sm:gap-2.5">
        <!-- Hidden File Input for JSON Import -->
        <input type="file" id="importFileInput" accept=".json,application/json" class="hidden" />

        <!-- Import JSON Button -->
        <button
          id="importJsonBtn"
          type="button"
          title="Import board state from JSON file"
          class="inline-flex items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 rounded-lg shadow-xs transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
        >
          <svg class="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          <span>Import JSON</span>
        </button>

        <!-- Export JSON Button -->
        <button
          id="exportJsonBtn"
          type="button"
          title="Export current board state to JSON file"
          class="inline-flex items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 rounded-lg shadow-xs transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
        >
          <svg class="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          <span>Export JSON</span>
        </button>

        <!-- + New Task Button -->
        <button
          id="newTaskHeaderBtn"
          type="button"
          class="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 rounded-lg shadow-sm shadow-indigo-500/25 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          <span>+ New Task</span>
        </button>
      </div>

    </div>
  </header>

  <!-- ==================== FILTER & SEARCH BAR ==================== -->
  <section class="bg-white border-b border-slate-200/80 px-4 sm:px-6 py-2.5 shrink-0 z-10 shadow-2xs">
    <div class="max-w-[1800px] mx-auto flex flex-wrap items-center justify-between gap-3">
      
      <!-- Live Search Input -->
      <div class="relative flex-1 min-w-[240px] max-w-md">
        <svg class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          id="searchInput"
          type="text"
          placeholder="Search tasks by title, description, or label..."
          autocomplete="off"
          class="w-full pl-9 pr-8 py-1.5 text-sm bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-slate-800 placeholder-slate-400 rounded-lg border border-slate-200 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all"
        />
        <button
          id="clearSearchIconBtn"
          type="button"
          title="Clear search text"
          class="hidden absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 rounded"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Priority Filter Chips & Clear Button -->
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs font-medium text-slate-400 uppercase tracking-wider mr-1 hidden md:inline">Priority:</span>

        <!-- Urgent (Red) -->
        <button
          type="button"
          data-priority="urgent"
          class="priority-chip inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all"
        >
          <span class="w-2 h-2 rounded-full bg-red-500"></span>
          <span>Urgent</span>
        </button>

        <!-- High (Orange) -->
        <button
          type="button"
          data-priority="high"
          class="priority-chip inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all"
        >
          <span class="w-2 h-2 rounded-full bg-orange-500"></span>
          <span>High</span>
        </button>

        <!-- Medium (Blue) -->
        <button
          type="button"
          data-priority="medium"
          class="priority-chip inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all"
        >
          <span class="w-2 h-2 rounded-full bg-blue-500"></span>
          <span>Medium</span>
        </button>

        <!-- Low (Gray) -->
        <button
          type="button"
          data-priority="low"
          class="priority-chip inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all"
        >
          <span class="w-2 h-2 rounded-full bg-slate-400"></span>
          <span>Low</span>
        </button>

        <div class="h-4 w-[1px] bg-slate-200 mx-0.5"></div>

        <!-- Clear Filters Button -->
        <button
          id="clearFiltersBtn"
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 disabled:opacity-40 disabled:pointer-events-none transition-all"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <span>Clear Filters</span>
        </button>
      </div>

    </div>
  </section>

  <!-- ==================== INTERACTIVE KANBAN BOARD ==================== -->
  <main class="flex-1 overflow-x-auto overflow-y-hidden p-4 sm:p-6">
    <div id="columnsContainer" class="h-full flex items-start gap-5 min-w-max pb-2">
      <!-- Columns and "+ Add Column" button are rendered dynamically here -->
    </div>
  </main>

  <!-- ==================== ADD / EDIT CARD MODAL ==================== -->
  <div
    id="cardModalBackdrop"
    class="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-40 hidden items-center justify-center p-4 opacity-0 transition-opacity duration-150"
    aria-hidden="true"
  >
    <div
      id="cardModalPanel"
      class="bg-white rounded-2xl shadow-2xl border border-slate-200/80 w-full max-w-lg overflow-hidden transform scale-95 transition-transform duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cardModalTitle"
    >
      <!-- Modal Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/60">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <h2 id="cardModalTitle" class="text-base font-bold text-slate-800">Create New Task</h2>
        </div>
        <button
          id="closeCardModalBtn"
          type="button"
          class="text-slate-400 hover:text-slate-600 hover:bg-slate-100 p-1.5 rounded-lg transition-colors"
          aria-label="Close modal"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Modal Form -->
      <form id="cardForm" class="p-6 space-y-4">
        <input type="hidden" id="cardIdInput" value="" />

        <!-- Title -->
        <div>
          <label for="cardTitleInput" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
            Task Title <span class="text-red-500">*</span>
          </label>
          <input
            id="cardTitleInput"
            type="text"
            required
            placeholder="e.g., Implement offline sync conflict resolver"
            class="w-full px-3.5 py-2 text-sm text-slate-900 bg-white border border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all"
          />
        </div>

        <!-- Description -->
        <div>
          <label for="cardDescInput" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
            Description
          </label>
          <textarea
            id="cardDescInput"
            rows="3"
            placeholder="Add context, acceptance criteria, or implementation notes..."
            class="w-full px-3.5 py-2 text-sm text-slate-900 bg-white border border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all resize-y"
          ></textarea>
        </div>

        <!-- Priority & Column Selector Row -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label for="cardPriorityInput" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Priority
            </label>
            <select
              id="cardPriorityInput"
              class="w-full px-3.5 py-2 text-sm text-slate-900 bg-white border border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all"
            >
              <option value="urgent">🔴 Urgent</option>
              <option value="high">🟠 High</option>
              <option value="medium" selected>🔵 Medium</option>
              <option value="low">⚪ Low</option>
            </select>
          </div>

          <div id="cardColumnSelectWrapper">
            <label for="cardColumnInput" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Column
            </label>
            <select
              id="cardColumnInput"
              class="w-full px-3.5 py-2 text-sm text-slate-900 bg-white border border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all"
            >
              <!-- Populated dynamically -->
            </select>
          </div>
        </div>

        <!-- Labels & Due Date Row -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label for="cardLabelsInput" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Labels <span class="text-slate-400 font-normal lowercase">(comma-separated)</span>
            </label>
            <input
              id="cardLabelsInput"
              type="text"
              placeholder="frontend, ui, v1.0"
              class="w-full px-3.5 py-2 text-sm text-slate-900 bg-white border border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all"
            />
          </div>

          <div>
            <label for="cardDueDateInput" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
              Due Date
            </label>
            <input
              id="cardDueDateInput"
              type="date"
              class="w-full px-3.5 py-2 text-sm text-slate-900 bg-white border border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all"
            />
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-end gap-2.5 pt-4 border-t border-slate-100">
          <button
            id="cancelCardModalBtn"
            type="button"
            class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200/80 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            id="saveCardSubmitBtn"
            class="px-5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 rounded-lg shadow-sm shadow-indigo-500/25 transition-all"
          >
            Save Task
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- ==================== ADD COLUMN MODAL ==================== -->
  <div
    id="columnModalBackdrop"
    class="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-40 hidden items-center justify-center p-4 opacity-0 transition-opacity duration-150"
    aria-hidden="true"
  >
    <div
      id="columnModalPanel"
      class="bg-white rounded-2xl shadow-2xl border border-slate-200/80 w-full max-w-sm overflow-hidden transform scale-95 transition-transform duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby="columnModalTitle"
    >
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/60">
        <h2 id="columnModalTitle" class="text-base font-bold text-slate-800">Add New Column</h2>
        <button
          id="closeColumnModalBtn"
          type="button"
          class="text-slate-400 hover:text-slate-600 hover:bg-slate-100 p-1.5 rounded-lg transition-colors"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <form id="columnForm" class="p-6 space-y-4">
        <div>
          <label for="columnNameInput" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
            Column Name <span class="text-red-500">*</span>
          </label>
          <input
            id="columnNameInput"
            type="text"
            required
            placeholder="e.g., QA Review, Blocked, Backlog"
            class="w-full px-3.5 py-2 text-sm text-slate-900 bg-white border border-slate-200 rounded-lg focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 transition-all"
          />
        </div>
        <div class="flex items-center justify-end gap-2.5 pt-2">
          <button
            id="cancelColumnModalBtn"
            type="button"
            class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200/80 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            class="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-sm shadow-indigo-500/25 transition-all"
          >
            Create Column
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- ==================== TOAST NOTIFICATION CONTAINER ==================== -->
  <div id="toastContainer" class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"></div>

  <!-- ==================== APPLICATION SCRIPT ==================== -->
  <script>
    /**
     * Fallback implementation of window.PulseTaskEngine ONLY if kanban_engine.js
     * is not present in the current directory (so index.html works standalone in any browser).
     * When kanban_engine.js is loaded, window.PulseTaskEngine is already defined and this block is skipped.
     */
    if (typeof window.PulseTaskEngine === 'undefined') {
      (function initFallbackEngine() {
        const STORAGE_KEY = 'pulsetask_state_v1';
        let listeners = [];
        let state = { schemaVersion: 1, boards: [] };

        try {
          const saved = localStorage.getItem(STORAGE_KEY);
          if (saved) {
            const parsed = JSON.parse(saved);
            if (parsed && Array.isArray(parsed.boards)) {
              state = parsed;
            }
          }
        } catch (err) {
          console.warn('PulseTask fallback storage read error:', err);
        }

        function persist(eventType, payload) {
          try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
          } catch (err) {
            console.warn('PulseTask fallback storage write error:', err);
          }
          listeners.forEach((cb) => {
            try {
              cb({ type: eventType, payload, state });
            } catch (e) {
              console.error(e);
            }
          });
        }

        function uid(prefix) {
          return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
        }

        function findColumnInfo(columnId) {
          for (const board of state.boards) {
            const colIndex = board.columns.findIndex((c) => c.id === columnId);
            if (colIndex !== -1) {
              return { board, col: board.columns[colIndex], colIndex };
            }
          }
          return null;
        }

        function findCardInfo(cardId) {
          for (const board of state.boards) {
            const card = Array.isArray(board.cards)
              ? board.cards.find((c) => c.id === cardId)
              : board.cards && board.cards[cardId];
            if (card) {
              const col = board.columns.find((c) => c.cardIds.includes(cardId));
              return { board, col, card };
            }
          }
          return null;
        }

        window.PulseTaskEngine = {
          createBoard(name) {
            const board = {
              id: uid('board'),
              name: String(name || 'Untitled Board').trim(),
              columns: [],
              cards: {}
            };
            state.boards.push(board);
            persist('board:create', board);
            return board;
          },

          getState() {
            return JSON.parse(JSON.stringify(state));
          },

          addColumn(boardId, name) {
            const board = state.boards.find((b) => b.id === boardId) || state.boards[0];
            if (!board) throw new Error('Board not found');
            const col = {
              id: uid('col'),
              name: String(name || 'New Column').trim(),
              cardIds: []
            };
            board.columns.push(col);
            persist('column:add', col);
            return col;
          },

          deleteColumn(columnId) {
            const info = findColumnInfo(columnId);
            if (!info) return;
            const { board, col, colIndex } = info;
            col.cardIds.forEach((cId) => {
              if (Array.isArray(board.cards)) {
                const idx = board.cards.findIndex((c) => c.id === cId);
                if (idx !== -1) board.cards.splice(idx, 1);
              } else if (board.cards) {
                delete board.cards[cId];
              }
            });
            board.columns.splice(colIndex, 1);
            persist('column:delete', { columnId });
          },

          addCard(columnId, data = {}) {
            const info = findColumnInfo(columnId);
            if (!info) throw new Error('Column not found');
            const { board, col } = info;
            const card = {
              id: uid('card'),
              title: String(data.title || 'Untitled Task').trim(),
              description: String(data.description || '').trim(),
              priority: ['urgent', 'high', 'medium', 'low'].includes(data.priority) ? data.priority : 'medium',
              labels: Array.isArray(data.labels) ? data.labels.map((l) => String(l).trim()).filter(Boolean) : [],
              dueDate: data.dueDate || ''
            };
            if (Array.isArray(board.cards)) {
              board.cards.push(card);
            } else {
              board.cards[card.id] = card;
            }
            col.cardIds.push(card.id);
            persist('card:add', card);
            return card;
          },

          updateCard(cardId, updates = {}) {
            const info = findCardInfo(cardId);
            if (!info) return null;
            const { card } = info;
            if (updates.title !== undefined) card.title = String(updates.title).trim();
            if (updates.description !== undefined) card.description = String(updates.description).trim();
            if (updates.priority !== undefined) card.priority = updates.priority;
            if (updates.labels !== undefined) {
              card.labels = Array.isArray(updates.labels)
                ? updates.labels.map((l) => String(l).trim()).filter(Boolean)
                : [];
            }
            if (updates.dueDate !== undefined) card.dueDate = updates.dueDate;
            persist('card:update', card);
            return card;
          },

          deleteCard(cardId) {
            const info = findCardInfo(cardId);
            if (!info) return;
            const { board, col } = info;
            if (col) {
              col.cardIds = col.cardIds.filter((id) => id !== cardId);
            }
            if (Array.isArray(board.cards)) {
              const idx = board.cards.findIndex((c) => c.id === cardId);
              if (idx !== -1) board.cards.splice(idx, 1);
            } else if (board.cards) {
              delete board.cards[cardId];
            }
            persist('card:delete', { cardId });
          },

          moveCard(cardId, targetColId, targetIndex) {
            const cardInfo = findCardInfo(cardId);
            const targetInfo = findColumnInfo(targetColId);
            if (!cardInfo || !targetInfo) return;
            const { col: sourceCol } = cardInfo;
            const { col: targetCol } = targetInfo;

            if (sourceCol) {
              const oldIdx = sourceCol.cardIds.indexOf(cardId);
              if (oldIdx !== -1) sourceCol.cardIds.splice(oldIdx, 1);
            }

            const boundedIdx =
              typeof targetIndex === 'number'
                ? Math.max(0, Math.min(targetIndex, targetCol.cardIds.length))
                : targetCol.cardIds.length;

            targetCol.cardIds.splice(boundedIdx, 0, cardId);
            persist('card:move', { cardId, targetColId, targetIndex: boundedIdx });
          },

          getVisibleCards(columnId, filters = {}, searchText = '') {
            const info = findColumnInfo(columnId);
            if (!info) return [];
            const { board, col } = info;
            const priorities = filters && Array.isArray(filters.priorities) ? filters.priorities : null;
            const q = String(searchText || '').trim().toLowerCase();

            return col.cardIds
              .map((id) =>
                Array.isArray(board.cards) ? board.cards.find((c) => c.id === id) : board.cards && board.cards[id]
              )
              .filter(Boolean)
              .filter((card) => {
                if (priorities && priorities.length > 0 && !priorities.includes(card.priority)) {
                  return false;
                }
                if (q) {
                  const inTitle = (card.title || '').toLowerCase().includes(q);
                  const inDesc = (card.description || '').toLowerCase().includes(q);
                  const inLabels = Array.isArray(card.labels) && card.labels.some((l) => l.toLowerCase().includes(q));
                  return inTitle || inDesc || inLabels;
                }
                return true;
              });
          },

          exportJSON() {
            return JSON.stringify(state, null, 2);
          },

          importJSON(jsonString) {
            const parsed = JSON.parse(jsonString);
            if (!parsed || !Array.isArray(parsed.boards)) {
              throw new Error('Invalid PulseTask JSON schema');
            }
            state = parsed;
            persist('state:import', state);
          },

          subscribe(callback) {
            if (typeof callback === 'function') {
              listeners.push(callback);
            }
            return () => {
              listeners = listeners.filter((cb) => cb !== callback);
            };
          }
        };
      })();
    }

    // =========================================================================
    // PULSETASK FRONTEND APPLICATION CONTROLLER
    // =========================================================================
    (function initPulseTaskApp() {
      const engine = window.PulseTaskEngine;

      // UI Filter & Drag State
      const uiState = {
        searchQuery: '',
        selectedPriorities: new Set(), // 'urgent' | 'high' | 'medium' | 'low'
        draggedCardId: null,
        dragSourceColId: null
      };

      // Priority Visual Theme Config
      const PRIORITY_STYLES = {
        urgent: {
          label: 'Urgent',
          badgeBg: 'bg-red-50 text-red-700 border-red-200/90',
          dot: 'bg-red-500',
          chipIdle: 'bg-white text-slate-600 border-slate-200 hover:border-red-300 hover:bg-red-50/50',
          chipActive: 'bg-red-600 text-white border-red-600 shadow-xs shadow-red-500/20',
          dotActive: 'bg-white'
        },
        high: {
          label: 'High',
          badgeBg: 'bg-orange-50 text-orange-700 border-orange-200/90',
          dot: 'bg-orange-500',
          chipIdle: 'bg-white text-slate-600 border-slate-200 hover:border-orange-300 hover:bg-orange-50/50',
          chipActive: 'bg-orange-500 text-white border-orange-500 shadow-xs shadow-orange-500/20',
          dotActive: 'bg-white'
        },
        medium: {
          label: 'Medium',
          badgeBg: 'bg-blue-50 text-blue-700 border-blue-200/90',
          dot: 'bg-blue-500',
          chipIdle: 'bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:bg-blue-50/50',
          chipActive: 'bg-blue-600 text-white border-blue-600 shadow-xs shadow-blue-500/20',
          dotActive: 'bg-white'
        },
        low: {
          label: 'Low',
          badgeBg: 'bg-slate-100 text-slate-600 border-slate-200/90',
          dot: 'bg-slate-400',
          chipIdle: 'bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:bg-slate-100/70',
          chipActive: 'bg-slate-700 text-white border-slate-700 shadow-xs shadow-slate-500/20',
          dotActive: 'bg-white'
        }
      };

      // DOM Elements
      const els = {
        boardTitleDisplay: document.getElementById('boardTitleDisplay'),
        totalTasksBadge: document.getElementById('totalTasksBadge'),
        newTaskHeaderBtn: document.getElementById('newTaskHeaderBtn'),
        exportJsonBtn: document.getElementById('exportJsonBtn'),
        importJsonBtn: document.getElementById('importJsonBtn'),
        importFileInput: document.getElementById('importFileInput'),
        searchInput: document.getElementById('searchInput'),
        clearSearchIconBtn: document.getElementById('clearSearchIconBtn'),
        priorityChips: document.querySelectorAll('.priority-chip'),
        clearFiltersBtn: document.getElementById('clearFiltersBtn'),
        columnsContainer: document.getElementById('columnsContainer'),

        // Card Modal
        cardModalBackdrop: document.getElementById('cardModalBackdrop'),
        cardModalPanel: document.getElementById('cardModalPanel'),
        cardModalTitle: document.getElementById('cardModalTitle'),
        closeCardModalBtn: document.getElementById('closeCardModalBtn'),
        cancelCardModalBtn: document.getElementById('cancelCardModalBtn'),
        cardForm: document.getElementById('cardForm'),
        cardIdInput: document.getElementById('cardIdInput'),
        cardTitleInput: document.getElementById('cardTitleInput'),
        cardDescInput: document.getElementById('cardDescInput'),
        cardPriorityInput: document.getElementById('cardPriorityInput'),
        cardColumnSelectWrapper: document.getElementById('cardColumnSelectWrapper'),
        cardColumnInput: document.getElementById('cardColumnInput'),
        cardLabelsInput: document.getElementById('cardLabelsInput'),
        cardDueDateInput: document.getElementById('cardDueDateInput'),
        saveCardSubmitBtn: document.getElementById('saveCardSubmitBtn'),

        // Column Modal
        columnModalBackdrop: document.getElementById('columnModalBackdrop'),
        columnModalPanel: document.getElementById('columnModalPanel'),
        closeColumnModalBtn: document.getElementById('closeColumnModalBtn'),
        cancelColumnModalBtn: document.getElementById('cancelColumnModalBtn'),
        columnForm: document.getElementById('columnForm'),
        columnNameInput: document.getElementById('columnNameInput'),

        // Toast Container
        toastContainer: document.getElementById('toastContainer')
      };

      // -----------------------------------------------------------------------
      // Helper Utilities
      // -----------------------------------------------------------------------
      function escapeHTML(str) {
        return String(str ?? '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
      }

      function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgClass =
          type === 'error'
            ? 'bg-red-600 text-white'
            : type === 'success'
            ? 'bg-slate-900 text-white'
            : 'bg-slate-800 text-white';

        toast.className = `pointer-events-auto flex items-center gap-2.5 px-4 py-2.5 rounded-xl shadow-lg text-xs sm:text-sm font-medium transform translate-y-2 opacity-0 transition-all duration-200 ${bgClass}`;
        toast.innerHTML = `
          <span>${escapeHTML(message)}</span>
        `;
        els.toastContainer.appendChild(toast);

        requestAnimationFrame(() => {
          toast.classList.remove('translate-y-2', 'opacity-0');
        });

        setTimeout(() => {
          toast.classList.add('translate-y-2', 'opacity-0');
          setTimeout(() => toast.remove(), 200);
        }, 2800);
      }

      function getActiveBoard() {
        const state = engine.getState();
        if (!state || !Array.isArray(state.boards) || state.boards.length === 0) {
          return null;
        }
        return state.boards[0];
      }

      function getBoardColumns(board) {
        if (!board || !board.columns) return [];
        return Array.isArray(board.columns) ? board.columns : Object.values(board.columns);
      }

      function findCardInBoard(board, cardId) {
        if (!board) return null;
        if (board.cards) {
          if (Array.isArray(board.cards)) {
            const found = board.cards.find((c) => c.id === cardId);
            if (found) return found;
          } else if (board.cards[cardId]) {
            return board.cards[cardId];
          }
        }
        // Fallback: query visible cards with empty filters across columns
        const cols = getBoardColumns(board);
        for (const col of cols) {
          const cards = queryVisibleCards(col, new Set(), '');
          const match = cards.find((c) => c.id === cardId);
          if (match) return match;
        }
        return null;
      }

      function findCardColumnId(board, cardId) {
        const cols = getBoardColumns(board);
        for (const col of cols) {
          if (Array.isArray(col.cardIds) && col.cardIds.includes(cardId)) {
            return col.id;
          }
        }
        return cols[0] ? cols[0].id : '';
      }

      function queryVisibleCards(column, selectedPrioritiesSet, searchQuery) {
        const prioritiesArr = Array.from(selectedPrioritiesSet);
        const hasPriorityFilter = prioritiesArr.length > 0;
        const allPriorities = ['urgent', 'high', 'medium', 'low'];

        try {
          const filterObj = hasPriorityFilter ? { priorities: prioritiesArr } : {};
          const res = engine.getVisibleCards(column.id, filterObj, searchQuery || '');
          // Handle engines that require non-empty priorities array when no filter is active
          if (
            !hasPriorityFilter &&
            !searchQuery &&
            Array.isArray(column.cardIds) &&
            column.cardIds.length > 0 &&
            (!res || res.length === 0)
          ) {
            return engine.getVisibleCards(column.id, { priorities: allPriorities }, searchQuery || '') || [];
          }
          return res || [];
        } catch (err) {
          const fallbackFilter = { priorities: hasPriorityFilter ? prioritiesArr : allPriorities };
          return engine.getVisibleCards(column.id, fallbackFilter, searchQuery || '') || [];
        }
      }

      function formatDueDateInfo(dueDateStr) {
        if (!dueDateStr) return null;
        const parts = String(dueDateStr).split('-');
        if (parts.length !== 3) {
          return { text: dueDateStr, classes: 'text-slate-500 bg-slate-100 border-slate-200' };
        }
        const year = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10) - 1;
        const day = parseInt(parts[2], 10);
        const dateObj = new Date(year, month, day);
        if (isNaN(dateObj.getTime())) {
          return { text: dueDateStr, classes: 'text-slate-500 bg-slate-100 border-slate-200' };
        }

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const diffDays = Math.round((dateObj - today) / (1000 * 60 * 60 * 24));

        const formatted = dateObj.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric'
        });

        if (diffDays < 0) {
          return {
            text: `${formatted} · Overdue`,
            classes: 'text-red-700 bg-red-50 border-red-200/80 font-medium'
          };
        }
        if (diffDays === 0) {
          return {
            text: `${formatted} · Today`,
            classes: 'text-amber-700 bg-amber-50 border-amber-200/80 font-medium'
          };
        }
        if (diffDays <= 2) {
          return {
            text: `${formatted} · Soon`,
            classes: 'text-indigo-700 bg-indigo-50 border-indigo-200/80'
          };
        }
        return {
          text: formatted,
          classes: 'text-slate-500 bg-slate-50 border-slate-200/80'
        };
      }

      // -----------------------------------------------------------------------
      // Auto-Seed Initial Data
      // -----------------------------------------------------------------------
      function seedInitialBoardIfEmpty() {
        const state = engine.getState();
        if (state && Array.isArray(state.boards) && state.boards.length > 0) {
          return;
        }

        const board = engine.createBoard('PulseTask Launch');
        const colTodo = engine.addColumn(board.id, 'To Do');
        const colInProgress = engine.addColumn(board.id, 'In Progress');
        const colDone = engine.addColumn(board.id, 'Done');

        // Helper for relative YYYY-MM-DD dates
        const offsetDate = (days) => {
          const d = new Date();
          d.setDate(d.getDate() + days);
          return d.toISOString().split('T')[0];
        };

        // 4 realistic tasks across Urgent, High, Medium, Low priorities
        engine.addCard(colTodo.id, {
          title: 'Resolve IndexedDB quota eviction edge case on Safari',
          description: 'Ensure local storage fallback triggers automatically and alerts the user before state payloads exceed browser quota limits.',
          priority: 'urgent',
          labels: ['storage', 'bugfix', 'safari'],
          dueDate: offsetDate(1)
        });

        engine.addCard(colTodo.id, {
          title: 'Design keyboard shortcut cheat-sheet overlay',
          description: 'Document quick keys for creating tasks, jumping to search, and clearing active priority filters.',
          priority: 'low',
          labels: ['ux', 'accessibility'],
          dueDate: offsetDate(6)
        });

        engine.addCard(colInProgress.id, {
          title: 'Implement HTML5 drag-and-drop card reordering',
          description: 'Support smooth cross-column transfers and intra-column index calculations with real-time visual drop indicators.',
          priority: 'high',
          labels: ['frontend', 'dnd', 'core'],
          dueDate: offsetDate(2)
        });

        engine.addCard(colDone.id, {
          title: 'Finalize PulseTask JSON schema v1 export/import spec',
          description: 'Validated deterministic serialization format with Claude and ChatGPT for zero-latency offline backups.',
          priority: 'medium',
          labels: ['architecture', 'schema'],
          dueDate: offsetDate(-1)
        });
      }

      // -----------------------------------------------------------------------
      // Render Pipeline
      // -----------------------------------------------------------------------
      function updateFilterBarUI() {
        // Priority chip toggle states
        els.priorityChips.forEach((chip) => {
          const p = chip.getAttribute('data-priority');
          const style = PRIORITY_STYLES[p] || PRIORITY_STYLES.medium;
          const isActive = uiState.selectedPriorities.has(p);
          const dotEl = chip.querySelector('span:first-child');

          chip.className = `priority-chip inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all cursor-pointer ${
            isActive ? style.chipActive : style.chipIdle
          }`;
          chip.setAttribute('aria-pressed', isActive ? 'true' : 'false');

          if (dotEl) {
            dotEl.className = `w-2 h-2 rounded-full ${isActive ? style.dotActive : style.dot}`;
          }
        });

        // Search clear icon visibility
        if (uiState.searchQuery.length > 0) {
          els.clearSearchIconBtn.classList.remove('hidden');
        } else {
          els.clearSearchIconBtn.classList.add('hidden');
        }

        // Clear Filters button state
        const hasFilters = uiState.searchQuery.trim().length > 0 || uiState.selectedPriorities.size > 0;
        els.clearFiltersBtn.disabled = !hasFilters;
      }

      function renderCardHTML(card, columnId) {
        const pKey = PRIORITY_STYLES[card.priority] ? card.priority : 'medium';
        const pStyle = PRIORITY_STYLES[pKey];
        const labels = Array.isArray(card.labels) ? card.labels.filter(Boolean) : [];
        const dueInfo = formatDueDateInfo(card.dueDate);

        const labelsHTML =
          labels.length > 0
            ? `<div class="flex flex-wrap gap-1.5 mt-3">
                ${labels
                  .map(
                    (tag) =>
                      `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-indigo-50/80 text-indigo-700 border border-indigo-100/90 font-mono">#${escapeHTML(
                        tag
                      )}</span>`
                  )
                  .join('')}
              </div>`
            : '';

        const dueHTML = dueInfo
          ? `<div class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] border ${dueInfo.classes}">
              <svg class="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span>${escapeHTML(dueInfo.text)}</span>
            </div>`
          : '';

        return `
          <article
            class="task-card group bg-white rounded-xl p-3.5 border border-slate-200/90 shadow-card hover:shadow-card-hover hover:border-indigo-300/80 cursor-grab active:cursor-grabbing relative"
            draggable="true"
            data-card-id="${escapeHTML(card.id)}"
            data-column-id="${escapeHTML(columnId)}"
          >
            <!-- Top Row: Priority Badge & Quick Actions -->
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold border ${pStyle.badgeBg}">
                <span class="w-1.5 h-1.5 rounded-full ${pStyle.dot}"></span>
                ${escapeHTML(pStyle.label)}
              </span>

              <div class="flex items-center gap-0.5 opacity-85 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  data-action="edit-card"
                  data-card-id="${escapeHTML(card.id)}"
                  title="Edit task"
                  class="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                >
                  <svg class="w-3.5 h-3.5 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
                <button
                  type="button"
                  data-action="delete-card"
                  data-card-id="${escapeHTML(card.id)}"
                  title="Delete task"
                  class="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <svg class="w-3.5 h-3.5 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Title -->
            <h3 class="text-sm font-semibold text-slate-800 leading-snug break-words">
              ${escapeHTML(card.title)}
            </h3>

            <!-- Description Preview -->
            ${
              card.description
                ? `<p class="text-xs text-slate-500 mt-1.5 leading-relaxed line-clamp-2 break-words">${escapeHTML(
                    card.description
                  )}</p>`
                : ''
            }

            <!-- Labels -->
            ${labelsHTML}

            <!-- Footer: Due Date -->
            ${
              dueHTML
                ? `<div class="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between">
                    ${dueHTML}
                  </div>`
                : ''
            }
          </article>
        `;
      }

      function render() {
        updateFilterBarUI();

        const board = getActiveBoard();
        if (!board) {
          els.boardTitleDisplay.textContent = 'No Active Board';
          els.totalTasksBadge.textContent = '0 tasks';
          els.columnsContainer.innerHTML = '';
          return;
        }

        els.boardTitleDisplay.textContent = board.name || 'PulseTask Board';

        const columns = getBoardColumns(board);
        const isFiltering = uiState.searchQuery.trim().length > 0 || uiState.selectedPriorities.size > 0;

        let totalBoardTasks = 0;
        columns.forEach((col) => {
          totalBoardTasks += Array.isArray(col.cardIds) ? col.cardIds.length : 0;
        });
        els.totalTasksBadge.textContent = `${totalBoardTasks} ${totalBoardTasks === 1 ? 'task' : 'tasks'}`;

        const columnsHTML = columns
          .map((col) => {
            const totalInCol = Array.isArray(col.cardIds) ? col.cardIds.length : 0;
            const visibleCards = queryVisibleCards(col, uiState.selectedPriorities, uiState.searchQuery);
            const countBadgeText = isFiltering
              ? `${visibleCards.length} of ${totalInCol} tasks`
              : `${visibleCards.length} ${visibleCards.length === 1 ? 'task' : 'tasks'}`;

            const cardsHTML =
              visibleCards.length > 0
                ? visibleCards.map((card) => renderCardHTML(card, col.id)).join('')
                : `<div class="empty-col-placeholder flex flex-col items-center justify-center py-10 px-4 text-center border-2 border-dashed border-slate-200/80 rounded-xl text-slate-400">
                    <svg class="w-7 h-7 mb-2 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    <p class="text-xs font-medium text-slate-500">${
                      isFiltering ? 'No matching tasks' : 'No tasks in this column'
                    }</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">${
                      isFiltering ? 'Try adjusting your filters' : 'Drop a card here or click + below'
                    }</p>
                  </div>`;

            return `
              <section
                class="kanban-column w-80 sm:w-[340px] shrink-0 max-h-full flex flex-col bg-slate-200/65 rounded-2xl border border-slate-200/90 shadow-2xs"
                data-column-id="${escapeHTML(col.id)}"
              >
                <!-- Column Header -->
                <div class="px-4 py-3 flex items-center justify-between gap-2 shrink-0">
                  <div class="flex items-center gap-2 min-w-0">
                    <h2 class="text-sm font-bold text-slate-800 truncate">${escapeHTML(col.name)}</h2>
                    <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-white text-slate-600 border border-slate-200/80 shadow-2xs shrink-0">
                      ${escapeHTML(countBadgeText)}
                    </span>
                  </div>

                  <div class="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      data-action="add-card-to-col"
                      data-column-id="${escapeHTML(col.id)}"
                      title="Add task to ${escapeHTML(col.name)}"
                      class="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-white rounded-lg transition-colors"
                    >
                      <svg class="w-4 h-4 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      data-action="delete-column"
                      data-column-id="${escapeHTML(col.id)}"
                      data-column-name="${escapeHTML(col.name)}"
                      title="Delete column"
                      class="p-1.5 text-slate-400 hover:text-red-600 hover:bg-white rounded-lg transition-colors"
                    >
                      <svg class="w-4 h-4 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>

                <!-- Column Cards Dropzone -->
                <div
                  class="column-dropzone flex-1 overflow-y-auto px-3 pb-3 space-y-2.5 rounded-b-2xl border-2 border-transparent min-h-[150px]"
                  data-dropzone-column-id="${escapeHTML(col.id)}"
                >
                  ${cardsHTML}
                </div>

                <!-- Column Footer Quick Add -->
                <div class="p-2.5 pt-1 shrink-0">
                  <button
                    type="button"
                    data-action="add-card-to-col"
                    data-column-id="${escapeHTML(col.id)}"
                    class="w-full py-2 px-3 rounded-xl text-xs font-semibold text-slate-600 hover:text-indigo-600 hover:bg-white/90 flex items-center justify-center gap-1.5 transition-all"
                  >
                    <svg class="w-3.5 h-3.5 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
                    </svg>
                    <span>Add Task</span>
                  </button>
                </div>
              </section>
            `;
          })
          .join('');

        // "+ Add Column" Button at the end of the horizontal board
        const addColumnButtonHTML = `
          <div class="w-72 shrink-0">
            <button
              type="button"
              id="addColumnTriggerBtn"
              data-action="open-add-column"
              class="w-full py-3.5 px-4 rounded-2xl border-2 border-dashed border-slate-300 hover:border-indigo-400 bg-white/50 hover:bg-white text-slate-600 hover:text-indigo-600 font-semibold text-sm flex items-center justify-center gap-2 transition-all shadow-2xs"
            >
              <svg class="w-4 h-4 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <span>+ Add Column</span>
            </button>
          </div>
        `;

        els.columnsContainer.innerHTML = columnsHTML + addColumnButtonHTML;
      }

      // -----------------------------------------------------------------------
      // Add / Edit Card Modal Logic
      // -----------------------------------------------------------------------
      function openCardModal({ mode = 'add', columnId = null, cardId = null } = {}) {
        const board = getActiveBoard();
        if (!board) return;
        const columns = getBoardColumns(board);

        if (columns.length === 0) {
          showToast('Please add a column first before creating a task.', 'error');
          openColumnModal();
          return;
        }

        // Populate column dropdown
        els.cardColumnInput.innerHTML = columns
          .map((c) => `<option value="${escapeHTML(c.id)}">${escapeHTML(c.name)}</option>`)
          .join('');

        if (mode === 'edit' && cardId) {
          const card = findCardInBoard(board, cardId);
          if (!card) return;
          const currentColumnId = findCardColumnId(board, cardId);

          els.cardModalTitle.textContent = 'Edit Task';
          els.saveCardSubmitBtn.textContent = 'Update Task';
          els.cardIdInput.value = card.id;
          els.cardTitleInput.value = card.title || '';
          els.cardDescInput.value = card.description || '';
          els.cardPriorityInput.value = ['urgent', 'high', 'medium', 'low'].includes(card.priority)
            ? card.priority
            : 'medium';
          els.cardColumnInput.value = currentColumnId;
          els.cardLabelsInput.value = Array.isArray(card.labels) ? card.labels.join(', ') : '';
          els.cardDueDateInput.value = card.dueDate || '';
        } else {
          els.cardModalTitle.textContent = 'Create New Task';
          els.saveCardSubmitBtn.textContent = 'Create Task';
          els.cardIdInput.value = '';
          els.cardTitleInput.value = '';
          els.cardDescInput.value = '';
          els.cardPriorityInput.value = 'medium';
          els.cardColumnInput.value = columnId || columns[0].id;
          els.cardLabelsInput.value = '';
          els.cardDueDateInput.value = '';
        }

        els.cardModalBackdrop.classList.remove('hidden');
        els.cardModalBackdrop.classList.add('flex');
        requestAnimationFrame(() => {
          els.cardModalBackdrop.classList.remove('opacity-0');
          els.cardModalPanel.classList.remove('scale-95');
          els.cardTitleInput.focus();
        });
      }

      function closeCardModal() {
        els.cardModalBackdrop.classList.add('opacity-0');
        els.cardModalPanel.classList.add('scale-95');
        setTimeout(() => {
          els.cardModalBackdrop.classList.remove('flex');
          els.cardModalBackdrop.classList.add('hidden');
        }, 150);
      }

      // -----------------------------------------------------------------------
      // Add Column Modal Logic
      // -----------------------------------------------------------------------
      function openColumnModal() {
        els.columnNameInput.value = '';
        els.columnModalBackdrop.classList.remove('hidden');
        els.columnModalBackdrop.classList.add('flex');
        requestAnimationFrame(() => {
          els.columnModalBackdrop.classList.remove('opacity-0');
          els.columnModalPanel.classList.remove('scale-95');
          els.columnNameInput.focus();
        });
      }

      function closeColumnModal() {
        els.columnModalBackdrop.classList.add('opacity-0');
        els.columnModalPanel.classList.add('scale-95');
        setTimeout(() => {
          els.columnModalBackdrop.classList.remove('flex');
          els.columnModalBackdrop.classList.add('hidden');
        }, 150);
      }

      // -----------------------------------------------------------------------
      // HTML5 Drag-and-Drop Implementation
      // -----------------------------------------------------------------------
      let activeDropIndicator = null;

      function removeDropIndicator() {
        if (activeDropIndicator && activeDropIndicator.parentNode) {
          activeDropIndicator.parentNode.removeChild(activeDropIndicator);
        }
        activeDropIndicator = null;
      }

      function clearAllDropzoneHighlights() {
        document.querySelectorAll('.column-dropzone.drag-over').forEach((el) => {
          el.classList.remove('drag-over');
        });
        removeDropIndicator();
      }

      /**
       * Computes both the insertion index for engine.moveCard() and the reference DOM node
       * before which the visual drop indicator should be placed.
       */
      function getDropPosition(dropzoneEl, clientY, draggedCardId) {
        const cardElements = Array.from(dropzoneEl.querySelectorAll('.task-card')).filter(
          (el) => el.getAttribute('data-card-id') !== draggedCardId
        );

        for (let i = 0; i < cardElements.length; i++) {
          const box = cardElements[i].getBoundingClientRect();
          const midpoint = box.top + box.height / 2;
          if (clientY < midpoint) {
            return { index: i, beforeElement: cardElements[i] };
          }
        }

        return { index: cardElements.length, beforeElement: null };
      }

      els.columnsContainer.addEventListener('dragstart', (e) => {
        const cardEl = e.target.closest('.task-card');
        if (!cardEl) return;

        const cardId = cardEl.getAttribute('data-card-id');
        const colId = cardEl.getAttribute('data-column-id');
        uiState.draggedCardId = cardId;
        uiState.dragSourceColId = colId;

        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', cardId);

        requestAnimationFrame(() => {
          cardEl.classList.add('is-dragging');
        });
      });

      els.columnsContainer.addEventListener('dragover', (e) => {
        const dropzoneEl = e.target.closest('.column-dropzone');
        if (!dropzoneEl || !uiState.draggedCardId) return;

        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        document.querySelectorAll('.column-dropzone.drag-over').forEach((el) => {
          if (el !== dropzoneEl) el.classList.remove('drag-over');
        });
        dropzoneEl.classList.add('drag-over');

        const { beforeElement } = getDropPosition(dropzoneEl, e.clientY, uiState.draggedCardId);

        if (!activeDropIndicator) {
          activeDropIndicator = document.createElement('div');
          activeDropIndicator.className = 'drop-indicator';
        }

        if (beforeElement) {
          dropzoneEl.insertBefore(activeDropIndicator, beforeElement);
        } else {
          dropzoneEl.appendChild(activeDropIndicator);
        }
      });

      els.columnsContainer.addEventListener('dragleave', (e) => {
        const dropzoneEl = e.target.closest('.column-dropzone');
        if (!dropzoneEl) return;

        const related = e.relatedTarget;
        if (!related || !dropzoneEl.contains(related)) {
          dropzoneEl.classList.remove('drag-over');
          if (activeDropIndicator && dropzoneEl.contains(activeDropIndicator)) {
            removeDropIndicator();
          }
        }
      });

      els.columnsContainer.addEventListener('drop', (e) => {
        const dropzoneEl = e.target.closest('.column-dropzone');
        if (!dropzoneEl) return;

        e.preventDefault();
        const cardId = uiState.draggedCardId || e.dataTransfer.getData('text/plain');
        const targetColId = dropzoneEl.getAttribute('data-dropzone-column-id');

        if (cardId && targetColId) {
          const { index: targetIndex } = getDropPosition(dropzoneEl, e.clientY, cardId);
          engine.moveCard(cardId, targetColId, targetIndex);
        }

        uiState.draggedCardId = null;
        uiState.dragSourceColId = null;
        clearAllDropzoneHighlights();
      });

      els.columnsContainer.addEventListener('dragend', () => {
        document.querySelectorAll('.task-card.is-dragging').forEach((el) => {
          el.classList.remove('is-dragging');
        });
        uiState.draggedCardId = null;
        uiState.dragSourceColId = null;
        clearAllDropzoneHighlights();
      });

      // -----------------------------------------------------------------------
      // Event Listeners: Board & Card Actions
      // -----------------------------------------------------------------------
      els.columnsContainer.addEventListener('click', (e) => {
        const actionBtn = e.target.closest('[data-action]');
        if (!actionBtn) return;

        const action = actionBtn.getAttribute('data-action');

        if (action === 'add-card-to-col') {
          const columnId = actionBtn.getAttribute('data-column-id');
          openCardModal({ mode: 'add', columnId });
        } else if (action === 'edit-card') {
          const cardId = actionBtn.getAttribute('data-card-id');
          openCardModal({ mode: 'edit', cardId });
        } else if (action === 'delete-card') {
          const cardId = actionBtn.getAttribute('data-card-id');
          engine.deleteCard(cardId);
          showToast('Task deleted');
        } else if (action === 'delete-column') {
          const columnId = actionBtn.getAttribute('data-column-id');
          const columnName = actionBtn.getAttribute('data-column-name') || 'this column';
          if (window.confirm(`Delete column "${columnName}" and all its tasks?`)) {
            engine.deleteColumn(columnId);
            showToast(`Deleted column "${columnName}"`);
          }
        } else if (action === 'open-add-column') {
          openColumnModal();
        }
      });

      // Header "+ New Task" button
      els.newTaskHeaderBtn.addEventListener('click', () => {
        openCardModal({ mode: 'add' });
      });

      // Card Form Submission (Create / Update)
      els.cardForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const cardId = els.cardIdInput.value.trim();
        const title = els.cardTitleInput.value.trim();
        if (!title) return;

        const description = els.cardDescInput.value.trim();
        const priority = els.cardPriorityInput.value;
        const targetColId = els.cardColumnInput.value;
        const labels = els.cardLabelsInput.value
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean);
        const dueDate = els.cardDueDateInput.value;

        const board = getActiveBoard();

        if (cardId) {
          const previousColId = findCardColumnId(board, cardId);
          engine.updateCard(cardId, { title, description, priority, labels, dueDate });
          if (targetColId && previousColId && targetColId !== previousColId) {
            const targetCol = getBoardColumns(board).find((c) => c.id === targetColId);
            const targetIdx = targetCol && Array.isArray(targetCol.cardIds) ? targetCol.cardIds.length : 0;
            engine.moveCard(cardId, targetColId, targetIdx);
          }
          showToast('Task updated', 'success');
        } else {
          engine.addCard(targetColId, {
            title,
            description,
            priority,
            labels,
            dueDate
          });
          showToast('Task created', 'success');
        }

        closeCardModal();
      });

      // Column Form Submission
      els.columnForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = els.columnNameInput.value.trim();
        if (!name) return;

        let board = getActiveBoard();
        if (!board) {
          board = engine.createBoard('PulseTask Launch');
        }
        engine.addColumn(board.id, name);
        showToast(`Added column "${name}"`, 'success');
        closeColumnModal();
      });

      // Modal Close Handlers
      els.closeCardModalBtn.addEventListener('click', closeCardModal);
      els.cancelCardModalBtn.addEventListener('click', closeCardModal);
      els.cardModalBackdrop.addEventListener('click', (e) => {
        if (e.target === els.cardModalBackdrop) closeCardModal();
      });

      els.closeColumnModalBtn.addEventListener('click', closeColumnModal);
      els.cancelColumnModalBtn.addEventListener('click', closeColumnModal);
      els.columnModalBackdrop.addEventListener('click', (e) => {
        if (e.target === els.columnModalBackdrop) closeColumnModal();
      });

      // Escape key closes open modals
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          if (!els.cardModalBackdrop.classList.contains('hidden')) closeCardModal();
          if (!els.columnModalBackdrop.classList.contains('hidden')) closeColumnModal();
        }
      });

      // -----------------------------------------------------------------------
      // Event Listeners: Live Search & Priority Filters
      // -----------------------------------------------------------------------
      els.searchInput.addEventListener('input', (e) => {
        uiState.searchQuery = e.target.value;
        render();
      });

      els.clearSearchIconBtn.addEventListener('click', () => {
        uiState.searchQuery = '';
        els.searchInput.value = '';
        els.searchInput.focus();
        render();
      });

      els.priorityChips.forEach((chip) => {
        chip.addEventListener('click', () => {
          const priority = chip.getAttribute('data-priority');
          if (!priority) return;
          if (uiState.selectedPriorities.has(priority)) {
            uiState.selectedPriorities.delete(priority);
          } else {
            uiState.selectedPriorities.add(priority);
          }
          render();
        });
      });

      els.clearFiltersBtn.addEventListener('click', () => {
        uiState.searchQuery = '';
        els.searchInput.value = '';
        uiState.selectedPriorities.clear();
        render();
      });

      // -----------------------------------------------------------------------
      // Event Listeners: Export & Import JSON
      // -----------------------------------------------------------------------
      els.exportJsonBtn.addEventListener('click', () => {
        try {
          const jsonString = engine.exportJSON();
          const blob = new Blob([jsonString], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          const dateStamp = new Date().toISOString().split('T')[0];
          a.href = url;
          a.download = `pulsetask-backup-${dateStamp}.json`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          showToast('Exported board JSON successfully', 'success');
        } catch (err) {
          console.error('Export JSON error:', err);
          showToast('Failed to export JSON', 'error');
        }
      });

      els.importJsonBtn.addEventListener('click', () => {
        els.importFileInput.value = '';
        els.importFileInput.click();
      });

      els.importFileInput.addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
          try {
            const content = String(event.target.result || '');
            engine.importJSON(content);
            render();
            showToast('Imported board JSON successfully', 'success');
          } catch (err) {
            console.error('Import JSON error:', err);
            showToast('Invalid JSON file format', 'error');
          }
        };
        reader.readAsText(file);
      });

      // -----------------------------------------------------------------------
      // Bootstrap: Subscribe to Realtime Engine Mutations & Seed Initial Data
      // -----------------------------------------------------------------------
      engine.subscribe(() => {
        render();
      });

      seedInitialBoardIfEmpty();
      render();
    })();
  </script>
</body>
</html>