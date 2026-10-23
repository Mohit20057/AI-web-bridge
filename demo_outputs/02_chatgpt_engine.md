Here is the complete standalone kanban_engine.js module for PulseTask, implementing the specified store, actions, filtering, local storage persistence, and JSON import/export.JavaScript
(function (root) {
  "use strict";

  const STORAGE_KEY = "pulsetask:data:v1";
  const SCHEMA_VERSION = 1;
  const PRIORITIES = ["urgent", "high", "medium", "low"];

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const isObject = (value) =>
    value !== null && typeof value === "object" && !Array.isArray(value);
  const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  const now = () => new Date().toISOString();

  function createId(prefix) {
    const cryptoObject = root.crypto;
    if (cryptoObject && typeof cryptoObject.randomUUID === "function") {
      return `${prefix}_${cryptoObject.randomUUID()}`;
    }
    return `${prefix}_${Date.now().toString(36)}_${Math.random()
      .toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`;
  }

  function requireString(value, field, allowEmpty = false) {
    if (typeof value !== "string") {
      throw new TypeError(`${field} must be a string.`);
    }
    const result = value.trim();
    if (!allowEmpty && !result) {
      throw new TypeError(`${field} cannot be empty.`);
    }
    return result;
  }

  function normalizePriority(value) {
    const priority = value == null ? "medium" : value;
    if (!PRIORITIES.includes(priority)) {
      throw new TypeError(`Priority must be one of: ${PRIORITIES.join(", ")}.`);
    }
    return priority;
  }

  function normalizeLabels(value) {
    if (value == null) return [];
    if (!Array.isArray(value)) throw new TypeError("labels must be an array.");
    return [...new Set(value.map((label) => requireString(label, "label")))];
  }

  function normalizeDueDate(value) {
    if (value == null || value === "") return null;
    if (typeof value !== "string") {
      throw new TypeError("dueDate must be a date string or null.");
    }

    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [year, month, day] = value.split("-").map(Number);
      const date = new Date(Date.UTC(year, month - 1, day));
      if (
        date.getUTCFullYear() !== year ||
        date.getUTCMonth() !== month - 1 ||
        date.getUTCDate() !== day
      ) {
        throw new TypeError("dueDate is not a valid calendar date.");
      }
      return value;
    }

    if (
      !/^\d{4}-\d{2}-\d{2}T/.test(value) ||
      Number.isNaN(Date.parse(value))
    ) {
      throw new TypeError("dueDate must be a valid ISO date or date-time.");
    }
    return value;
  }

  function normalizeTimestamp(value, fallback) {
    if (value == null) return fallback;
    if (typeof value !== "string" || Number.isNaN(Date.parse(value))) {
      throw new TypeError("createdAt/updatedAt must be a valid date string.");
    }
    return value;
  }

  function initialState() {
    return { schemaVersion: SCHEMA_VERSION, boards: [] };
  }

  function normalizeState(input) {
    if (!isObject(input) || !Array.isArray(input.boards)) {
      throw new TypeError("Imported data must contain a boards array.");
    }
    if (
      input.schemaVersion !== undefined &&
      input.schemaVersion !== SCHEMA_VERSION
    ) {
      throw new TypeError(`Unsupported schema version: ${input.schemaVersion}.`);
    }

    const result = initialState();
    const ids = new Set();
    const timestamp = now();

    function registerId(value, type) {
      const id = requireString(value, `${type}.id`);
      if (ids.has(id)) throw new TypeError(`Duplicate ID: ${id}`);
      ids.add(id);
      return id;
    }

    for (const rawBoard of input.boards) {
      if (
        !isObject(rawBoard) ||
        !Array.isArray(rawBoard.columns) ||
        !Array.isArray(rawBoard.cards)
      ) {
        throw new TypeError("Each board must contain columns and cards arrays.");
      }

      const board = {
        id: registerId(rawBoard.id, "board"),
        name: requireString(rawBoard.name, "board.name"),
        createdAt: normalizeTimestamp(rawBoard.createdAt, timestamp),
        updatedAt: normalizeTimestamp(rawBoard.updatedAt, timestamp),
        columns: [],
        cards: [],
      };

      const cardsById = new Map();

      for (const rawCard of rawBoard.cards) {
        if (!isObject(rawCard)) throw new TypeError("Invalid card object.");

        const card = {
          id: registerId(rawCard.id, "card"),
          title: requireString(rawCard.title, "card.title"),
          description: rawCard.description == null
            ? ""
            : requireString(rawCard.description, "card.description", true),
          priority: normalizePriority(rawCard.priority),
          labels: normalizeLabels(rawCard.labels),
          dueDate: normalizeDueDate(rawCard.dueDate),
          createdAt: normalizeTimestamp(rawCard.createdAt, timestamp),
        };

        board.cards.push(card);
        cardsById.set(card.id, card);
      }

      const assigned = new Set();

      for (const rawColumn of rawBoard.columns) {
        if (!isObject(rawColumn) || !Array.isArray(rawColumn.cardIds)) {
          throw new TypeError("Each column must contain a cardIds array.");
        }

        const column = {
          id: registerId(rawColumn.id, "column"),
          name: requireString(rawColumn.name, "column.name"),
          cardIds: [],
        };

        // Discard stale and repeated references during import.
        for (const cardId of rawColumn.cardIds) {
          if (
            typeof cardId === "string" &&
            cardsById.has(cardId) &&
            !assigned.has(cardId)
          ) {
            column.cardIds.push(cardId);
            assigned.add(cardId);
          }
        }
        board.columns.push(column);
      }

      for (const card of board.cards) {
        if (!assigned.has(card.id)) {
          throw new TypeError(`Card "${card.id}" has no column.`);
        }
      }

      result.boards.push(board);
    }

    return result;
  }

  let state = initialState();
  let lastStorageError = null;
  const listeners = new Set();

  function emit(type, details = {}) {
    const event = { type, ...details, state: getState() };
    for (const listener of [...listeners]) {
      try {
        listener(event);
      } catch (error) {
        console.error("[PulseTask] Subscriber error:", error);
      }
    }
  }

  function findBoard(boardId) {
    return state.boards.find((board) => board.id === boardId) || null;
  }

  function requireBoard(boardId) {
    const board = findBoard(boardId);
    if (!board) throw new Error(`Board "${boardId}" was not found.`);
    return board;
  }

  function findColumn(columnId) {
    for (const board of state.boards) {
      const column = board.columns.find((item) => item.id === columnId);
      if (column) return { board, column };
    }
    return null;
  }

  function findCard(cardId) {
    for (const board of state.boards) {
      const card = board.cards.find((item) => item.id === cardId);
      if (card) return { board, card };
    }
    return null;
  }

  function idExists(id) {
    return state.boards.some((board) =>
      board.id === id ||
      board.columns.some((column) => column.id === id) ||
      board.cards.some((card) => card.id === id)
    );
  }

  function touch(board) {
    board.updatedAt = now();
  }

  function persistMutation(type, details) {
    const persisted = saveData();
    emit(type, { ...details, persisted });
  }

  function getState() {
    return clone(state);
  }

  function getBoard(boardId) {
    const board = findBoard(boardId);
    return board ? clone(board) : null;
  }

  function getColumn(columnId) {
    const result = findColumn(columnId);
    return result ? clone(result.column) : null;
  }

  function getCard(cardId) {
    const result = findCard(cardId);
    return result ? clone(result.card) : null;
  }

  function createBoard(input) {
    const data = typeof input === "string" ? { name: input } : input;
    if (!isObject(data)) throw new TypeError("Provide a board name or object.");

    const timestamp = now();
    const board = {
      id: data.id === undefined ? createId("board") : requireString(data.id, "id"),
      name: requireString(data.name, "board.name"),
      createdAt: timestamp,
      updatedAt: timestamp,
      columns: [],
      cards: [],
    };

    if (idExists(board.id)) throw new Error(`ID "${board.id}" already exists.`);
    state.boards.push(board);
    persistMutation("board:created", { boardId: board.id });
    return clone(board);
  }

  function addColumn(boardId, input) {
    const board = requireBoard(boardId);
    const data = typeof input === "string" ? { name: input } : input;
    if (!isObject(data)) throw new TypeError("Provide a column name or object.");

    const column = {
      id: data.id === undefined ? createId("column") : requireString(data.id, "id"),
      name: requireString(data.name, "column.name"),
      cardIds: [],
    };

    if (idExists(column.id)) throw new Error(`ID "${column.id}" already exists.`);
    board.columns.push(column);
    touch(board);
    persistMutation("column:created", { boardId, columnId: column.id });
    return clone(column);
  }

  function deleteColumn(columnId) {
    const result = findColumn(columnId);
    if (!result) throw new Error(`Column "${columnId}" was not found.`);

    const { board, column } = result;
    const deletedCardIds = new Set(column.cardIds);

    board.columns = board.columns.filter((item) => item.id !== columnId);
    board.cards = board.cards.filter((card) => !deletedCardIds.has(card.id));
    touch(board);

    persistMutation("column:deleted", {
      boardId: board.id,
      columnId,
      deletedCardIds: [...deletedCardIds],
    });
    return true;
  }

  function addCard(columnId, cardData) {
    const result = findColumn(columnId);
    if (!result) throw new Error(`Column "${columnId}" was not found.`);
    if (!isObject(cardData)) throw new TypeError("cardData must be an object.");

    const { board, column } = result;
    const card = {
      id: cardData.id === undefined ? createId("card") : requireString(cardData.id, "id"),
      title: requireString(cardData.title, "card.title"),
      description: cardData.description == null
        ? ""
        : requireString(cardData.description, "card.description", true),
      priority: normalizePriority(cardData.priority),
      labels: normalizeLabels(cardData.labels),
      dueDate: normalizeDueDate(cardData.dueDate),
      createdAt: normalizeTimestamp(cardData.createdAt, now()),
    };

    if (idExists(card.id)) throw new Error(`ID "${card.id}" already exists.`);
    board.cards.push(card);
    column.cardIds.push(card.id);
    touch(board);

    persistMutation("card:created", {
      boardId: board.id,
      columnId,
      cardId: card.id,
    });
    return clone(card);
  }

  function updateCard(cardId, patch) {
    const result = findCard(cardId);
    if (!result) throw new Error(`Card "${cardId}" was not found.`);
    if (!isObject(patch)) throw new TypeError("patch must be an object.");

    const allowed = new Set(["title", "description", "priority", "labels", "dueDate"]);
    const normalized = {};

    for (const key of Object.keys(patch)) {
      if (!allowed.has(key)) throw new TypeError(`Unsupported card field: ${key}`);
    }

    if (hasOwn(patch, "title")) {
      normalized.title = requireString(patch.title, "card.title");
    }
    if (hasOwn(patch, "description")) {
      normalized.description = patch.description == null
        ? ""
        : requireString(patch.description, "card.description", true);
    }
    if (hasOwn(patch, "priority")) {
      normalized.priority = normalizePriority(patch.priority);
    }
    if (hasOwn(patch, "labels")) {
      normalized.labels = normalizeLabels(patch.labels);
    }
    if (hasOwn(patch, "dueDate")) {
      normalized.dueDate = normalizeDueDate(patch.dueDate);
    }

    Object.assign(result.card, normalized);
    touch(result.board);
    persistMutation("card:updated", {
      boardId: result.board.id,
      cardId,
      fields: Object.keys(normalized),
    });
    return clone(result.card);
  }

  function deleteCard(cardId) {
    const result = findCard(cardId);
    if (!result) throw new Error(`Card "${cardId}" was not found.`);

    const { board } = result;
    board.cards = board.cards.filter((card) => card.id !== cardId);
    for (const column of board.columns) {
      column.cardIds = column.cardIds.filter((id) => id !== cardId);
    }
    touch(board);

    persistMutation("card:deleted", { boardId: board.id, cardId });
    return true;
  }

  function moveCard(cardId, targetColId, targetIndex) {
    const source = findCard(cardId);
    const destination = findColumn(targetColId);

    if (!source) throw new Error(`Card "${cardId}" was not found.`);
    if (!destination) throw new Error(`Column "${targetColId}" was not found.`);
    if (source.board.id !== destination.board.id) {
      throw new Error("Cards cannot be moved between different boards.");
    }
    if (targetIndex !== undefined && !Number.isInteger(targetIndex)) {
      throw new TypeError("targetIndex must be an integer.");
    }

    const board = source.board;
    const sourceColumn = board.columns.find((column) =>
      column.cardIds.includes(cardId)
    );
    if (!sourceColumn) throw new Error(`Card "${cardId}" has no source column.`);

    const sourceIndex = sourceColumn.cardIds.indexOf(cardId);
    sourceColumn.cardIds.splice(sourceIndex, 1);

    let index = targetIndex === undefined
      ? destination.column.cardIds.length
      : targetIndex;

    index = Math.max(0, Math.min(index, destination.column.cardIds.length));
    destination.column.cardIds.splice(index, 0, cardId);
    touch(board);

    persistMutation("card:moved", {
      boardId: board.id,
      cardId,
      sourceColumnId: sourceColumn.id,
      targetColumnId: targetColId,
      targetIndex: index,
    });

    return { card: clone(source.card), columnId: targetColId, index };
  }

  function getVisibleCards(columnId, filters = {}, search = "") {
    const result = findColumn(columnId);
    if (!result) return [];
    if (!isObject(filters)) throw new TypeError("filters must be an object.");
    if (typeof search !== "string") throw new TypeError("search must be a string.");

    const { board, column } = result;
    const cardsById = new Map(board.cards.map((card) => [card.id, card]));

    let priorities = null;
    if (filters.priorities !== undefined) {
      if (!Array.isArray(filters.priorities)) {
        throw new TypeError("filters.priorities must be an array.");
      }
      priorities = filters.priorities.map(normalizePriority);
    } else if (filters.priority !== undefined) {
      priorities = [normalizePriority(filters.priority)];
    }

    const labels = filters.labels === undefined ? [] : normalizeLabels(filters.labels);
    const labelMode = filters.labelMode || "all";
    if (!["all", "any"].includes(labelMode)) {
      throw new TypeError('labelMode must be "all" or "any".');
    }

    const dueBefore = filters.dueBefore == null ? null : normalizeDueDate(filters.dueBefore);
    const dueAfter = filters.dueAfter == null ? null : normalizeDueDate(filters.dueAfter);
    const dueDate = filters.dueDate == null ? null : normalizeDueDate(filters.dueDate);
    const query = search.trim().toLocaleLowerCase();

    return column.cardIds
      .map((id) => cardsById.get(id))
      .filter(Boolean)
      .filter((card) => {
        if (priorities && !priorities.includes(card.priority)) return false;

        if (labels.length) {
          const cardLabels = new Set(card.labels);
          const matches = labelMode === "all"
            ? labels.every((label) => cardLabels.has(label))
            : labels.some((label) => cardLabels.has(label));
          if (!matches) return false;
        }

        if (filters.hasDueDate === true && !card.dueDate) return false;
        if (filters.hasDueDate === false && card.dueDate) return false;

        const cardDate = card.dueDate ? card.dueDate.slice(0, 10) : null;
        if (dueDate && cardDate !== dueDate.slice(0, 10)) return false;
        if (dueBefore && (!cardDate || cardDate > dueBefore.slice(0, 10))) return false;
        if (dueAfter && (!cardDate || cardDate < dueAfter.slice(0, 10))) return false;

        if (query) {
          const searchable = [
            card.title,
            card.description,
            ...card.labels,
          ].join(" ").toLocaleLowerCase();

          if (!searchable.includes(query)) return false;
        }

        return true;
      })
      .map(clone);
  }

  function ensureStorage() {
    if (
      !root.localStorage ||
      typeof root.localStorage.getItem !== "function" ||
      typeof root.localStorage.setItem !== "function"
    ) {
      throw new Error("localStorage is unavailable.");
    }
  }

  function loadData() {
    ensureStorage();
    const raw = root.localStorage.getItem(STORAGE_KEY);

    if (raw === null) {
      state = initialState();
      emit("data:loaded", { source: "empty" });
      return getState();
    }

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      throw new Error(`Saved data contains invalid JSON: ${error.message}`);
    }

    state = normalizeState(parsed);
    emit("data:loaded", { source: "localStorage" });
    return getState();
  }

  function saveData() {
    try {
      ensureStorage();
      root.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      lastStorageError = null;
      return true;
    } catch (error) {
      lastStorageError = error;
      console.error("[PulseTask] Failed to save data:", error);
      return false;
    }
  }

  function exportJSON(space = 2) {
    if (!Number.isInteger(space) || space < 0 || space > 10) {
      throw new TypeError("Indentation must be an integer from 0 to 10.");
    }
    return JSON.stringify(state, null, space);
  }

  function importJSON(jsonString, options = {}) {
    if (typeof jsonString !== "string") {
      throw new TypeError("importJSON expects a JSON string.");
    }
    if (!isObject(options)) throw new TypeError("options must be an object.");

    let parsed;
    try {
      parsed = JSON.parse(jsonString);
    } catch (error) {
      throw new Error(`Invalid JSON: ${error.message}`);
    }

    // Validate before replacing current state.
    const imported = normalizeState(parsed);
    state = imported;

    const persisted = options.persist === false ? null : saveData();
    emit("data:imported", { persisted });
    return { state: getState(), persisted };
  }

  function subscribe(listener) {
    if (typeof listener !== "function") {
      throw new TypeError("Listener must be a function.");
    }
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function unsubscribe(listener) {
    return listeners.delete(listener);
  }

  function reset(options = {}) {
    if (!isObject(options)) throw new TypeError("options must be an object.");
    state = initialState();

    let persisted = null;
    if (options.clearStorage === true) {
      try {
        ensureStorage();
        root.localStorage.removeItem(STORAGE_KEY);
        lastStorageError = null;
        persisted = true;
      } catch (error) {
        lastStorageError = error;
        persisted = false;
      }
    } else if (options.persist === true) {
      persisted = saveData();
    }

    emit("data:reset", { persisted });
    return getState();
  }

  const api = {
    STORAGE_KEY,
    SCHEMA_VERSION,
    PRIORITIES: Object.freeze([...PRIORITIES]),

    createBoard,
    addColumn,
    deleteColumn,
    addCard,
    updateCard,
    deleteCard,
    moveCard,
    getVisibleCards,

    loadData,
    saveData,
    exportJSON,
    importJSON,

    getState,
    getBoard,
    getColumn,
    getCard,

    subscribe,
    unsubscribe,
    getLastStorageError: () => lastStorageError,
    reset,
  };

  root.PulseTaskEngine = Object.freeze(api);

  // Restore saved state when the script loads.
  try {
    if (
      root.localStorage &&
      root.localStorage.getItem(STORAGE_KEY) !== null
    ) {
      loadData();
    }
  } catch (error) {
    console.error("[PulseTask] Startup loading failed:", error);
  }
})(typeof window !== "undefined" ? window : globalThis);
UsageJavaScriptconst engine = window.PulseTaskEngine;

const board = engine.createBoard("Sprint Planning");
const todo = engine.addColumn(board.id, "To Do");
const doing = engine.addColumn(board.id, "In Progress");

const card = engine.addCard(todo.id, {
  title: "Build authentication API",
  description: "Implement JWT authentication",
  priority: "high",
  labels: ["backend", "security"],
  dueDate: "2026-12-31",
});

engine.updateCard(card.id, { priority: "urgent" });

console.log(
  engine.getVisibleCards(todo.id, { priority: "urgent" }, "authentication")
);

engine.moveCard(card.id, doing.id, 0);

const backup = engine.exportJSON();
engine.importJSON(backup);

const unsubscribe = engine.subscribe((event) => {
  console.log(event.type, event.state);
});
unsubscribe();Behavior: deleting a column also deletes its cards; card moves are restricted to columns on the same board; mutations automatically attempt persistence; and invalid imports leave the previous state unchanged.