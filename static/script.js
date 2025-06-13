// Audio Downloader Frontend v2.0
let ws = null;
let authToken = null;
let isAuthenticated = false;
let connectionId = null;  // Track our WebSocket connection ID
// Fallback polling if WebSocket disconnects
let fallbackPollID = null;
const fallbackPollInterval = 30000; // ms

// Initialize WebSocket connection
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
        // Stop fallback polling when WS reconnects
        if (fallbackPollID) {
            clearInterval(fallbackPollID);
            fallbackPollID = null;
        }
        // Don't clear jobs immediately - let loadJobs handle updates
        // Reload jobs after reconnect with cleanup
        setTimeout(() => {
            loadJobsWithCleanup();
        }, 100);
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        
        if (message.type === 'connection_established') {
            connectionId = message.connection_id;
            console.log('WebSocket connection established with ID:', connectionId);
        } else if (message.type === 'job_update') {
            updateJobInList(message.job_id, message.data);
            
            // Track job status changes
            if (typeof posthog !== 'undefined') {
                if (message.data.status === 'completed') {
                    posthog.capture('download_completed', {
                        job_id: message.job_id,
                        download_mode: message.data.download_mode,
                        tracks_count: message.data.progress?.total || 0
                    });
                } else if (message.data.status === 'error') {
                    posthog.capture('download_failed', {
                        job_id: message.job_id,
                        error_message: message.data.message
                    });
                }
            }
            
            // If a server download completes, refresh the server downloads list
            if (message.data.download_mode === 'server' && 
                (message.data.status === 'completed' || message.data.status === 'error')) {
                if (isAuthenticated) {
                    loadServerDownloads();
                }
            }
        }
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
        connectionId = null;  // Reset connection ID
        // Start fallback polling
        if (!fallbackPollID) {
            fallbackPollID = setInterval(loadJobs, fallbackPollInterval);
        }
        // Reconnect after 3 seconds
        setTimeout(initWebSocket, 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (statusEl) {
        statusEl.textContent = connected ? '🟢 Connected' : '🔴 Disconnected';
    }
}

// Authentication
async function login() {
    const password = document.getElementById('admin-password').value;
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        
        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            isAuthenticated = true;
            localStorage.setItem('authToken', authToken);
            showAuthenticatedUI();
            showNotification('Login successful!', 'success');
            
            // Track successful login
            if (typeof posthog !== 'undefined') {
                posthog.capture('user_logged_in');
                posthog.identify('admin'); // Since we only have one user type
            }
        } else {
            showNotification('Invalid password', 'error');
            
            // Track failed login
            if (typeof posthog !== 'undefined') {
                posthog.capture('login_failed');
            }
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('Login failed', 'error');
    }
}

function logout() {
    authToken = null;
    isAuthenticated = false;
    localStorage.removeItem('authToken');
    showUnauthenticatedUI();
    showNotification('Logged out', 'info');
    
    // Track logout
    if (typeof posthog !== 'undefined') {
        posthog.capture('user_logged_out');
        posthog.reset(); // Clear the identified user
    }
}

function showAuthenticatedUI() {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('server-mode-option').style.display = 'block';
    document.getElementById('server-downloads-section').style.display = 'block';
    // Show download mode selector for admin
    document.getElementById('download-mode-group').style.display = 'block';
    loadServerDownloads();
    // Hide or show workers input based on current mode
    const wg = document.getElementById('workers-group');
    const mode = document.getElementById('download-mode').value;
    wg.style.display = (mode === 'server') ? 'block' : 'none';
}

function showUnauthenticatedUI() {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('server-mode-option').style.display = 'none';
    document.getElementById('server-downloads-section').style.display = 'none';
    // Hide download mode selector for guests
    document.getElementById('download-mode-group').style.display = 'none';
    document.getElementById('download-mode').value = 'browser';
    // Ensure workers input is hidden
    const wg2 = document.getElementById('workers-group');
    wg2.style.display = 'none';
}

// Download functionality
async function startDownload() {
    const url = document.getElementById('url').value;
    const name = document.getElementById('name').value;
    const plugin = document.getElementById('plugin').value;
    const workers = parseInt(document.getElementById('workers').value) || 5;
    const downloadMode = document.getElementById('download-mode').value;
    
    if (!url) {
        showNotification('Please enter a URL', 'error');
        return;
    }
    
    // Track download attempt
    if (typeof posthog !== 'undefined') {
        posthog.capture('download_started', {
            url_domain: new URL(url).hostname,
            plugin: plugin || 'auto-detect',
            workers: workers,
            download_mode: downloadMode,
            has_custom_name: !!name,
            is_authenticated: isAuthenticated
        });
    }
    
    const requestData = {
        url,
        name: name || null,
        plugin: plugin || null,
        workers,
        download_mode: downloadMode,
        auth_token: downloadMode === 'server' ? authToken : null,
        connection_id: connectionId  // Include our WebSocket connection ID
    };
    
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });
        
        if (response.ok) {
            const job = await response.json();
            addJobToList(job);
            
            // Track successful download start
            if (typeof posthog !== 'undefined') {
                posthog.capture('download_initiated', {
                    job_id: job.job_id,
                    download_mode: downloadMode
                });
            }
            
            // Clear form
            document.getElementById('url').value = '';
            document.getElementById('name').value = '';
            
            if (downloadMode === 'browser') {
                showNotification('Processing... Download will start automatically in a few seconds!', 'success');
            } else {
                showNotification('Download started! Files will be saved to the server.', 'success');
            }
        } else {
            const error = await response.json();
            let errorMessage = error.detail || 'Failed to start download';
            
            // Track download error
            if (typeof posthog !== 'undefined') {
                posthog.capture('download_error', {
                    error_type: response.status === 429 ? 'rate_limit' : 'other',
                    status_code: response.status,
                    error_message: errorMessage
                });
            }
            
            // Handle rate limit errors specifically
            if (response.status === 429) {
                errorMessage = 'Rate limit exceeded. Please wait a minute before trying again.';
                
                // Disable submit button temporarily with countdown
                const submitBtn = document.querySelector('button[onclick="submitDownload()"]');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    let secondsLeft = 60;
                    
                    // Update button text with countdown
                    const updateCountdown = () => {
                        submitBtn.textContent = `Rate Limited - Wait ${secondsLeft}s`;
                        secondsLeft--;
                        
                        if (secondsLeft <= 0) {
                            clearInterval(countdownInterval);
                            submitBtn.disabled = false;
                            submitBtn.textContent = 'Start Download';
                        }
                    };
                    
                    updateCountdown(); // Initial update
                    const countdownInterval = setInterval(updateCountdown, 1000);
                }
            }
            
            showNotification(errorMessage, 'error');
        }
    } catch (error) {
        console.error('Download error:', error);
        showNotification('Failed to start download', 'error');
    }
}

// Job management
function addJobToList(job) {
    const jobsList = document.getElementById('jobs-list');
    const jobElement = createJobElement(job);
    jobsList.insertBefore(jobElement, jobsList.firstChild);
    
    // Don't auto-download here - let updateJobInList handle it when status changes
}

function updateJobInList(jobId, jobData) {
    const jobElement = document.getElementById(`job-${jobId}`);
    if (jobElement) {
        // Ensure job_id is included in the data for createJobElement
        const jobDataWithId = { ...jobData, job_id: jobId };
        const updatedElement = createJobElement(jobDataWithId);
        jobElement.replaceWith(updatedElement);
    } else {
        // If job doesn't exist in list, add it
        const jobDataWithId = { ...jobData, job_id: jobId };
        addJobToList(jobDataWithId);
    }
    
    // Auto-start download when job is ready for streaming
    if (jobData.status === 'streaming' && jobData.download_mode === 'browser') {
        // Only trigger download if explicitly marked by server AND not already downloaded
        if (jobData.auto_download === true && !autoDownloadedJobs.has(jobId)) {
            autoDownloadedJobs.add(jobId);
            localStorage.setItem('autoDownloadedJobs', JSON.stringify([...autoDownloadedJobs]));
            console.log(`Job ${jobId} marked for auto-download by server`);
            
            // Add a small delay to ensure UI updates
            setTimeout(() => {
                streamDownload(jobId);
            }, 500);
        }
    }
}

function createJobElement(job) {
    const div = document.createElement('div');
    div.id = `job-${job.job_id}`;
    div.className = `job-item ${job.status}`;
    
    let progressHtml = '';
    if (job.progress) {
        const percentage = Math.round((job.progress.completed / job.progress.total) * 100);
        progressHtml = `
            <div class="progress-container">
                <div class="progress-bar" style="width: ${percentage}%"></div>
                <span class="progress-text">${job.progress.completed}/${job.progress.total} tracks (${percentage}%)</span>
            </div>
        `;
    }
    
    let actionsHtml = '';
    if (job.status === 'pending' || job.status === 'detecting') {
        actionsHtml = `<button onclick="cancelJob('${job.job_id}')" class="btn-cancel">Cancel</button>`;
    } else if (job.status === 'downloading') {
        if (job.download_mode === 'browser') {
            actionsHtml = `<span class="downloading-status">📥 Streaming to your browser...</span>`;
        } else {
            actionsHtml = `<span class="downloading-status">💾 Saving to server...</span>`;
        }
    } else if (job.status === 'streaming' && job.download_mode === 'browser') {
        actionsHtml = `
            <span class="streaming-status">✅ Ready!</span>
            <button onclick="streamDownload('${job.job_id}')" class="btn-download">Download Now</button>
            <button onclick="cancelJob('${job.job_id}')" class="btn-cancel">Cancel</button>
        `;
    } else if (job.status === 'completed' || job.status === 'error' || job.status === 'cancelled') {
        actionsHtml = `<button onclick="clearJob('${job.job_id}')" class="btn-clear">Clear</button>`;
    }
    
    div.innerHTML = `
        <div class="job-header">
            <span class="job-name">${job.download_name || 'Unnamed'}</span>
            <span class="job-status ${job.status}">${job.status}</span>
            <span class="job-mode">${job.download_mode || 'browser'}</span>
        </div>
        <div class="job-message">${job.message || ''}</div>
        ${progressHtml}
        <div class="job-actions">${actionsHtml}</div>
        <div class="job-time">${formatTime(job.created_at)}</div>
    `;
    
    return div;
}

// Track which jobs have auto-downloaded (persisted in localStorage)
const autoDownloadedJobs = new Set(JSON.parse(localStorage.getItem('autoDownloadedJobs') || '[]'));
// Track which downloads are in progress
const downloadsInProgress = new Set();

// Listen for storage changes from other tabs
window.addEventListener('storage', (e) => {
    if (e.key === 'autoDownloadedJobs') {
        const updated = JSON.parse(e.newValue || '[]');
        autoDownloadedJobs.clear();
        updated.forEach(jobId => autoDownloadedJobs.add(jobId));
        console.log('Auto-downloaded jobs updated from another tab:', updated);
    }
});

async function streamDownload(jobId) {
    // Prevent multiple simultaneous downloads of the same job
    if (downloadsInProgress.has(jobId)) {
        console.log(`Download already in progress for job ${jobId}`);
        return;
    }
    
    downloadsInProgress.add(jobId);
    console.log(`Starting download for job ${jobId}`);
    
    // Create a hidden link and click it to start download
    const link = document.createElement('a');
    link.href = `/api/stream/${jobId}`;
    link.download = true;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showNotification('🎉 ZIP file downloading! Check your browser\'s Downloads folder.', 'success');
    
    // Remove from in-progress after a delay
    setTimeout(() => {
        downloadsInProgress.delete(jobId);
    }, 5000);
}

async function cancelJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
        if (response.ok) {
            showNotification('Job cancelled', 'info');
        }
    } catch (error) {
        console.error('Cancel error:', error);
    }
}

async function clearJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
        if (response.ok) {
            document.getElementById(`job-${jobId}`).remove();
        }
    } catch (error) {
        console.error('Clear error:', error);
    }
}

// Server downloads management
async function loadServerDownloads() {
    if (!isAuthenticated) return;
    
    try {
        const response = await fetch(`/api/downloads?auth_token=${authToken}`);
        if (response.ok) {
            const downloads = await response.json();
            displayServerDownloads(downloads);
        }
    } catch (error) {
        console.error('Load downloads error:', error);
    }
}

function displayServerDownloads(downloads) {
    const container = document.getElementById('server-downloads-list');
    container.innerHTML = '';
    
    if (downloads.length === 0) {
        container.innerHTML = '<p>No server downloads yet</p>';
        return;
    }
    
    downloads.forEach(download => {
        const div = document.createElement('div');
        div.className = 'download-item';
        div.innerHTML = `
            <div class="download-info">
                <span class="download-name">${download.name}</span>
                <span class="download-stats">${download.files} files, ${formatSize(download.size)}</span>
                <span class="download-time">${formatTime(download.created)}</span>
            </div>
            <div class="download-actions">
                <button onclick="downloadAsZip('${download.name}')" class="btn-download">Download ZIP</button>
                <button onclick="deleteDownload('${download.name}')" class="btn-delete">Delete</button>
            </div>
        `;
        container.appendChild(div);
    });
}

async function downloadAsZip(name) {
    window.open(`/api/downloads/${name}/zip?auth_token=${authToken}`);
}

async function deleteDownload(name) {
    if (!confirm(`Delete download "${name}"?`)) return;
    
    try {
        const response = await fetch(`/api/downloads/${name}?auth_token=${authToken}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            showNotification('Download deleted', 'info');
            loadServerDownloads();
        }
    } catch (error) {
        console.error('Delete error:', error);
    }
}

// Utility functions
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.getElementById('notifications').appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function formatSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// Auto-cleanup stale streaming jobs (older than 10 minutes)
function cleanupStaleJobs() {
    const staleTime = 10 * 60 * 1000; // 10 minutes
    const now = new Date();
    
    document.querySelectorAll('.job-item.streaming').forEach(jobElement => {
        const timeElement = jobElement.querySelector('.job-time');
        if (timeElement) {
            const jobTime = new Date(timeElement.textContent);
            if (now - jobTime > staleTime) {
                const jobId = jobElement.id.replace('job-', '');
                console.log(`Auto-canceling stale streaming job: ${jobId}`);
                cancelJob(jobId);
            }
        }
    });
    
    // Also cleanup completed/error/cancelled jobs older than 30 minutes
    const completedStaleTime = 30 * 60 * 1000; // 30 minutes
    document.querySelectorAll('.job-item.completed, .job-item.error, .job-item.cancelled').forEach(jobElement => {
        const timeElement = jobElement.querySelector('.job-time');
        if (timeElement) {
            const jobTime = new Date(timeElement.textContent);
            if (now - jobTime > completedStaleTime) {
                const jobId = jobElement.id.replace('job-', '');
                console.log(`Auto-clearing old completed job: ${jobId}`);
                clearJob(jobId);
            }
        }
    });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit for PostHog to initialize
    setTimeout(() => {
        if (typeof posthog !== 'undefined') {
            console.log('PostHog loaded successfully');
            posthog.capture('$pageview');
            
            // Send a test event to verify integration
            posthog.capture('audiofetch_loaded', {
                timestamp: new Date().toISOString(),
                user_agent: navigator.userAgent
            });
        } else {
            console.error('PostHog not loaded - check browser console for errors');
        }
    }, 1000);
    
    // Clean up old download locks from localStorage
    Object.keys(localStorage).forEach(key => {
        if (key.startsWith('downloading_')) {
            localStorage.removeItem(key);
        }
    });
    
    // Check for saved auth token
    const savedToken = localStorage.getItem('authToken');
    if (savedToken) {
        authToken = savedToken;
        isAuthenticated = true;
        showAuthenticatedUI();
    } else {
        showUnauthenticatedUI();
    }
    
    // Initialize WebSocket
    initWebSocket();
    
    // Run cleanup check on page load
    cleanupStaleJobs();
    
    // Run cleanup check every minute
    setInterval(cleanupStaleJobs, 60000);
    
    // Toggle download mode & workers inputs based on auth & mode selection
    const workersGroup = document.getElementById('workers-group');
    const downloadModeSelect = document.getElementById('download-mode');
    const dmGroup = document.getElementById('download-mode-group');
    function toggleWorkersGroup() {
        if (downloadModeSelect.value === 'server') workersGroup.style.display = 'block';
        else workersGroup.style.display = 'none';
    }
    function toggleDownloadModeGroup() {
        if (isAuthenticated) dmGroup.style.display = 'block';
        else dmGroup.style.display = 'none';
    }
    downloadModeSelect.addEventListener('change', toggleWorkersGroup);
    
    // Secret trigger: double-click logo to reveal login
    const logo = document.querySelector('.logo-container');
    if (logo) {
        logo.addEventListener('dblclick', () => {
            const authSection = document.getElementById('auth-section');
            authSection.style.display = authSection.style.display === 'block' ? 'none' : 'block';
        });
    }
    // Initial hide/show
    toggleDownloadModeGroup();
    toggleWorkersGroup();
    
    // Load initial jobs
    loadJobs();
    
    // Fallback polling removed; rely on WebSocket updates and slow fallback on disconnect
    // If still needed, use loadJobs() manually after initial load
});

async function loadJobs() {
    try {
        const response = await fetch('/api/jobs');
        if (response.ok) {
            const jobs = await response.json();
            const jobsList = document.getElementById('jobs-list');
            
            // Only clear and re-add if this is the first load
            if (jobsList.children.length === 0) {
                jobs.forEach(job => {
                    addJobToList(job);
                    // Mark existing streaming jobs as already downloaded
                    if (job.status === 'streaming' && job.download_mode === 'browser') {
                        autoDownloadedJobs.add(job.job_id);
                    }
                });
            } else {
                // Update existing jobs
                jobs.forEach(job => {
                    const existing = document.getElementById(`job-${job.job_id}`);
                    if (!existing) {
                        addJobToList(job);
                    }
                });
            }
        }
    } catch (error) {
        console.error('Load jobs error:', error);
    }
}

async function loadJobsWithCleanup() {
    try {
        const response = await fetch('/api/jobs');
        if (response.ok) {
            const jobs = await response.json();
            const jobsList = document.getElementById('jobs-list');
            
            // Get all current job IDs from server
            const serverJobIds = new Set(jobs.map(job => job.job_id));
            
            // Remove any jobs from UI that are no longer on server
            Array.from(jobsList.children).forEach(jobElement => {
                const jobId = jobElement.id.replace('job-', '');
                if (!serverJobIds.has(jobId)) {
                    console.log(`Removing orphaned job from UI: ${jobId}`);
                    jobElement.remove();
                }
            });
            
            // Update or add jobs from server
            jobs.forEach(job => {
                updateJobInList(job.job_id, job);
            });
            
            // Run cleanup for stale jobs
            cleanupStaleJobs();
        }
    } catch (error) {
        console.error('Load jobs with cleanup error:', error);
    }
}