// ── API Helper with Retry Logic ──────────────────────────────────

const API_MAX_RETRIES = 2;
const API_RETRY_DELAY_MS = 500;

/**
 * Centralized fetch wrapper with automatic retry for transient failures.
 * Retries on network errors and 5xx responses with exponential backoff.
 */
async function apiFetch(url, options = {}) {
    let lastError;
    for (let attempt = 0; attempt <= API_MAX_RETRIES; attempt++) {
        try {
            const response = await fetch(url, options);
            // Don't retry client errors (4xx) — only server errors (5xx)
            if (response.ok || (response.status >= 400 && response.status < 500)) {
                return response;
            }
            lastError = new Error(`Server error: ${response.status}`);
        } catch (err) {
            lastError = err;
        }
        // Exponential backoff before retry
        if (attempt < API_MAX_RETRIES) {
            await new Promise(r => setTimeout(r, API_RETRY_DELAY_MS * Math.pow(2, attempt)));
        }
    }
    throw lastError;
}

// ── Debounce Guard ───────────────────────────────────────────────

const _pendingActions = new Set();

/**
 * Prevents duplicate rapid submissions. Returns true if the action
 * is already in-flight, false otherwise (and registers it).
 */
function isActionPending(key) {
    if (_pendingActions.has(key)) return true;
    _pendingActions.add(key);
    return false;
}

function clearActionPending(key) {
    _pendingActions.delete(key);
}

// ── Offline / Online Detection ───────────────────────────────────

window.addEventListener('offline', () => showToast('You are offline — changes may not save.', 'error'));
window.addEventListener('online', () => showToast('Back online.', 'info'));

// ── App State ────────────────────────────────────────────────────

let state = {
    lists: [],
    activeListId: null,
    activeFilter: 'all', // 'all', 'active', 'completed'
    editingTaskId: null,
    renamingListId: null
};

// AbortController for cancelling in-flight task fetches
let _taskFetchController = null;

// DOM Elements
const listsNav = document.getElementById('lists-nav');
const newListInput = document.getElementById('new-list-input');
const currentSpaceTitle = document.getElementById('current-space-title');
const taskCount = document.getElementById('task-count');
const tasksList = document.getElementById('tasks-list');
const newTaskForm = document.getElementById('new-task-form');
const newTaskInput = document.getElementById('new-task-input');
const newTaskDate = document.getElementById('new-task-date');
const filterLinks = document.querySelectorAll('.filter-link');

// Initialize App
async function init() {
    setupEventListeners();
    await fetchLists();
    
    // Load previously selected space from localStorage if exists
    const storedListId = localStorage.getItem('activeListId');
    const parsedId = parseInt(storedListId, 10);
    if (!isNaN(parsedId) && state.lists.some(l => l.id === parsedId)) {
        state.activeListId = parsedId;
    } else if (state.lists.length > 0) {
        state.activeListId = state.lists[0].id;
    }
    
    await updateUI();
}

// Event Listeners Setup
function setupEventListeners() {
    // New list creation on Enter
    newListInput.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const listName = newListInput.value.trim();
            if (listName) {
                await createList(listName);
                newListInput.value = '';
            }
        }
    });

    // New task creation form submit
    newTaskForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = newTaskInput.value.trim();
        const dueDate = newTaskDate.value ? new Date(newTaskDate.value).toISOString() : null;
        
        if (title && state.activeListId) {
            await createTask(title, dueDate, state.activeListId);
            newTaskInput.value = '';
            newTaskDate.value = '';
        }
    });

    // Filter switching
    filterLinks.forEach(link => {
        link.addEventListener('click', async (e) => {
            filterLinks.forEach(l => l.classList.remove('active'));
            e.target.classList.add('active');
            state.activeFilter = e.target.dataset.filter;
            await renderTasks();
        });
    });
}

// --- API Calls ---

async function fetchLists() {
    try {
        const response = await apiFetch('/api/lists');
        if (!response.ok) {
            console.error('Failed to fetch lists:', response.status);
            return;
        }
        state.lists = await response.json();
        renderLists();
    } catch (err) {
        console.error('Error fetching lists:', err);
        showToast('Failed to load spaces. Please refresh.', 'error');
    }
}

async function createList(name) {
    if (isActionPending('createList')) return;
    try {
        const response = await apiFetch('/api/lists', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (response.ok || response.status === 201) {
            const newList = await response.json();
            state.lists.push(newList);
            state.activeListId = newList.id;
            localStorage.setItem('activeListId', newList.id);
            updateUI();
        } else {
            const errData = await response.json();
            showToast(errData.detail || 'Failed to create space', 'error');
        }
    } catch (err) {
        console.error('Error creating list:', err);
        showToast('Network error — could not create space.', 'error');
    } finally {
        clearActionPending('createList');
    }
}

async function renameList(id, newName) {
    try {
        const response = await apiFetch(`/api/lists/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        if (response.ok) {
            const updatedList = await response.json();
            const idx = state.lists.findIndex(l => l.id === id);
            if (idx !== -1) state.lists[idx] = updatedList;
            state.renamingListId = null;
            updateUI();
        } else {
            const errData = await response.json();
            showToast(errData.detail || 'Failed to rename space', 'error');
        }
    } catch (err) {
        console.error('Error renaming list:', err);
        showToast('Network error — could not rename space.', 'error');
    }
}

async function deleteList(id, name) {
    if (!confirm(`Are you sure you want to delete the space "${name}" and all of its tasks?`)) {
        return;
    }
    try {
        const response = await apiFetch(`/api/lists/${id}`, { method: 'DELETE' });
        if (response.ok) {
            state.lists = state.lists.filter(l => l.id !== id);
            if (state.activeListId === id) {
                state.activeListId = state.lists.length > 0 ? state.lists[0].id : null;
                if (state.activeListId) {
                    localStorage.setItem('activeListId', state.activeListId);
                } else {
                    localStorage.removeItem('activeListId');
                }
            }
            updateUI();
        } else {
            showToast('Failed to delete space', 'error');
        }
    } catch (err) {
        console.error('Error deleting list:', err);
        showToast('Network error — could not delete space.', 'error');
    }
}

async function fetchTasks() {
    if (!state.activeListId) {
        tasksList.innerHTML = '<div class="empty-state"><p>Create a space to start tracking tasks.</p></div>';
        taskCount.textContent = '0 tasks';
        return [];
    }

    // Cancel any in-flight task fetch to prevent stale data races
    if (_taskFetchController) {
        _taskFetchController.abort();
    }
    _taskFetchController = new AbortController();

    try {
        const response = await apiFetch(`/api/tasks?list_id=${state.activeListId}`, {
            signal: _taskFetchController.signal
        });
        if (!response.ok) {
            console.error('Failed to fetch tasks:', response.status);
            return [];
        }
        return await response.json();
    } catch (err) {
        // Don't show error toast for intentional aborts
        if (err.name === 'AbortError') return [];
        console.error('Error fetching tasks:', err);
        showToast('Failed to load tasks. Please refresh.', 'error');
        return [];
    }
}

async function createTask(title, dueDate, listId) {
    if (isActionPending('createTask')) return;
    try {
        const response = await apiFetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                due_date: dueDate,
                list_id: listId
            })
        });
        if (response.ok || response.status === 201) {
            updateUI();
        } else {
            const errData = await response.json();
            showToast(errData.detail || 'Failed to create task', 'error');
        }
    } catch (err) {
        console.error('Error creating task:', err);
        showToast('Network error — could not create task.', 'error');
    } finally {
        clearActionPending('createTask');
    }
}

async function toggleTaskComplete(id, isCompleted) {
    try {
        const response = await apiFetch(`/api/tasks/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_completed: isCompleted })
        });
        if (!response.ok) {
            showToast('Failed to update task', 'error');
        }
        updateUI();
    } catch (err) {
        console.error('Error toggling task:', err);
        showToast('Network error — could not update task.', 'error');
    }
}

async function updateTaskDetails(id, title, dueDate, listId) {
    try {
        const response = await apiFetch(`/api/tasks/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                due_date: dueDate ? new Date(dueDate).toISOString() : null,
                list_id: parseInt(listId)
            })
        });
        if (response.ok) {
            state.editingTaskId = null;
            updateUI();
        } else {
            const errData = await response.json();
            showToast(errData.detail || 'Failed to update task', 'error');
        }
    } catch (err) {
        console.error('Error updating task:', err);
        showToast('Network error — could not update task.', 'error');
    }
}

async function deleteTask(id) {
    try {
        const response = await apiFetch(`/api/tasks/${id}`, { method: 'DELETE' });
        if (response.ok) {
            updateUI();
        } else {
            showToast('Failed to delete task', 'error');
        }
    } catch (err) {
        console.error('Error deleting task:', err);
        showToast('Network error — could not delete task.', 'error');
    }
}

// --- Render / UI Updates ---

async function updateUI() {
    renderLists();
    
    // Update Active List Header
    const activeList = state.lists.find(l => l.id === state.activeListId);
    if (activeList) {
        currentSpaceTitle.textContent = activeList.name;
        newTaskInput.placeholder = `Add a task to ${activeList.name}... Press Enter to save`;
    } else {
        currentSpaceTitle.textContent = 'Select a Space';
        newTaskInput.placeholder = 'Select a space first';
    }
    
    await renderTasks();
}

function renderLists() {
    listsNav.innerHTML = '';
    
    state.lists.forEach(list => {
        const li = document.createElement('li');
        li.className = `nav-item ${list.id === state.activeListId ? 'active' : ''}`;
        li.dataset.id = list.id;
        
        if (state.renamingListId === list.id) {
            // Render inline rename input
            const renameInput = document.createElement('input');
            renameInput.type = 'text';
            renameInput.value = list.name;
            renameInput.maxLength = 50;
            renameInput.className = 'rename-list-input';
            renameInput.addEventListener('keypress', async (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const newName = renameInput.value.trim();
                    if (newName && newName !== list.name) {
                        await renameList(list.id, newName);
                    } else {
                        state.renamingListId = null;
                        renderLists();
                    }
                }
            });
            renameInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    state.renamingListId = null;
                    renderLists();
                }
            });
            renameInput.addEventListener('blur', () => {
                state.renamingListId = null;
                renderLists();
            });
            li.appendChild(renameInput);
            // Auto-focus after render
            requestAnimationFrame(() => {
                renameInput.focus();
                renameInput.select();
            });
        } else {
            const contentSpan = document.createElement('span');
            contentSpan.className = 'nav-item-content';
            contentSpan.innerHTML = `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                </svg>
                ${escapeHtml(list.name)}
            `;
            
            li.appendChild(contentSpan);
            
            // Actions (except for Inbox — it is protected)
            if (list.name.toLowerCase() !== 'inbox') {
                const actionsContainer = document.createElement('div');
                actionsContainer.className = 'nav-item-actions';
                
                // Rename button
                const renameBtn = document.createElement('button');
                renameBtn.className = 'rename-list-btn';
                renameBtn.setAttribute('aria-label', `Rename space ${list.name}`);
                renameBtn.innerHTML = `
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                `;
                renameBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    state.renamingListId = list.id;
                    renderLists();
                });
                actionsContainer.appendChild(renameBtn);
                
                // Delete button
                const delBtn = document.createElement('button');
                delBtn.className = 'delete-list-btn';
                delBtn.setAttribute('aria-label', `Delete space ${list.name}`);
                delBtn.innerHTML = `
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                `;
                delBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteList(list.id, list.name);
                });
                actionsContainer.appendChild(delBtn);
                
                li.appendChild(actionsContainer);
            }
            
            li.addEventListener('click', () => {
                state.activeListId = list.id;
                localStorage.setItem('activeListId', list.id);
                state.editingTaskId = null;
                updateUI();
            });
        }
        
        listsNav.appendChild(li);
    });
}

async function renderTasks() {
    const rawTasks = await fetchTasks();
    
    // Apply client-side filters
    let filteredTasks = rawTasks;
    if (state.activeFilter === 'active') {
        filteredTasks = rawTasks.filter(t => !t.is_completed);
    } else if (state.activeFilter === 'completed') {
        filteredTasks = rawTasks.filter(t => t.is_completed);
    }
    
    // Sort tasks: Active first (sub-sorted by due date / ID), Completed last
    filteredTasks.sort((a, b) => {
        if (a.is_completed !== b.is_completed) {
            return a.is_completed ? 1 : -1;
        }
        if (a.due_date && b.due_date) {
            return new Date(a.due_date) - new Date(b.due_date);
        }
        if (a.due_date) return -1;
        if (b.due_date) return 1;
        return a.id - b.id;
    });
    
    taskCount.textContent = `${filteredTasks.length} task${filteredTasks.length === 1 ? '' : 's'}`;
    
    tasksList.innerHTML = '';
    
    if (filteredTasks.length === 0) {
        const emptyMsg = state.activeFilter !== 'all'
            ? `No ${state.activeFilter} tasks here.`
            : 'No tasks yet. Type above to add one.';
        tasksList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                        <polyline points="10 9 9 9 8 9"></polyline>
                    </svg>
                </div>
                <p>${emptyMsg}</p>
            </div>
        `;
        return;
    }
    
    filteredTasks.forEach(task => {
        const isTaskEditing = (task.id === state.editingTaskId);
        
        const card = document.createElement('div');
        card.className = `task-card ${task.is_completed ? 'completed' : ''}`;
        
        if (isTaskEditing) {
            // Render Inline Edit View
            const localDate = task.due_date ? formatDateTimeLocal(task.due_date) : '';
            
            card.innerHTML = `
                <form class="task-edit-form" id="edit-form-${task.id}">
                    <input type="text" class="task-edit-title-input" id="edit-title-${task.id}" value="${escapeAttr(task.title)}" required maxlength="500">
                    <div class="task-edit-row">
                        <div class="option-group">
                            <label>Due</label>
                            <input type="datetime-local" class="date-input" id="edit-date-${task.id}" value="${localDate}">
                        </div>
                        <div class="option-group">
                            <label>Move to</label>
                            <select class="task-edit-select" id="edit-list-${task.id}">
                                ${state.lists.map(l => `
                                    <option value="${l.id}" ${l.id === task.list_id ? 'selected' : ''}>
                                        ${escapeHtml(l.name)}
                                    </option>
                                `).join('')}
                            </select>
                        </div>
                    </div>
                    <div class="task-edit-actions">
                        <button type="submit" class="edit-action-btn save">Save</button>
                        <button type="button" class="edit-action-btn cancel" id="cancel-edit-${task.id}">Cancel</button>
                    </div>
                </form>
            `;
            
            // Attach form submission & cancel listeners
            const editForm = card.querySelector(`#edit-form-${task.id}`);
            editForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const newTitle = document.getElementById(`edit-title-${task.id}`).value.trim();
                const newDateVal = document.getElementById(`edit-date-${task.id}`).value;
                const newListId = document.getElementById(`edit-list-${task.id}`).value;
                
                if (!newTitle) return;
                await updateTaskDetails(task.id, newTitle, newDateVal, newListId);
            });
            
            const cancelBtn = card.querySelector(`#cancel-edit-${task.id}`);
            cancelBtn.addEventListener('click', () => {
                state.editingTaskId = null;
                renderTasks();
            });
            
            // Auto-focus the title input
            requestAnimationFrame(() => {
                const titleInput = card.querySelector(`#edit-title-${task.id}`);
                if (titleInput) titleInput.focus();
            });
            
        } else {
            // Render Normal view
            const hasPassed = isOverdue(task.due_date, task.is_completed);
            const formattedDate = formatDueDate(task.due_date);
            const matchedList = state.lists.find(l => l.id === task.list_id);
            const listName = matchedList ? matchedList.name : '';
            
            card.innerHTML = `
                <div class="checkbox-wrapper">
                    <input type="checkbox" class="custom-checkbox" ${task.is_completed ? 'checked' : ''}>
                    <div class="checkbox-visual"></div>
                </div>
                <div class="task-content">
                    <div class="task-title-container">
                        <span class="task-title">${escapeHtml(task.title)}</span>
                    </div>
                    <div class="task-meta">
                        ${formattedDate ? `
                            <span class="task-due ${hasPassed ? 'overdue' : ''}">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="16" y1="2" x2="16" y2="6"></line>
                                    <line x1="8" y1="2" x2="8" y2="6"></line>
                                    <line x1="3" y1="10" x2="21" y2="10"></line>
                                </svg>
                                ${formattedDate} ${hasPassed ? '(Overdue)' : ''}
                            </span>
                        ` : ''}
                        <span class="task-space-badge">${escapeHtml(listName)}</span>
                    </div>
                </div>
                <button class="task-delete-btn" aria-label="Delete task">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        <line x1="10" y1="11" x2="10" y2="17"></line>
                        <line x1="14" y1="11" x2="14" y2="17"></line>
                    </svg>
                </button>
            `;
            
            // Event bindings
            const checkbox = card.querySelector('.custom-checkbox');
            checkbox.addEventListener('change', (e) => {
                toggleTaskComplete(task.id, e.target.checked);
            });
            
            const titleContainer = card.querySelector('.task-title-container');
            titleContainer.addEventListener('click', () => {
                state.editingTaskId = task.id;
                renderTasks();
            });
            
            const delBtn = card.querySelector('.task-delete-btn');
            delBtn.addEventListener('click', () => {
                deleteTask(task.id);
            });
        }
        
        tasksList.appendChild(card);
    });
}

// --- Toast Notification ---

function showToast(message, type = 'info') {
    // Remove any existing toast
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Trigger reflow for animation
    requestAnimationFrame(() => toast.classList.add('visible'));
    
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- Helpers ---

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Escape for HTML attribute values (e.g. input value="...")
function escapeAttr(str) {
    if (!str) return '';
    return str
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function isOverdue(dueDateStr, isCompleted) {
    if (!dueDateStr || isCompleted) return false;
    const dueDate = new Date(dueDateStr);
    const now = new Date();
    return dueDate < now;
}

function formatDueDate(dueDateStr) {
    if (!dueDateStr) return "";
    const date = new Date(dueDateStr);
    return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDateTimeLocal(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    // Format to yyyy-MM-ddThh:mm for datetime-local value
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Run init
document.addEventListener('DOMContentLoaded', init);
