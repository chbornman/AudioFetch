// API base URL
const API_BASE = '/api';

// Store active job IDs for polling
const activeJobs = new Set();

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('downloadForm');
    form.addEventListener('submit', handleFormSubmit);
    
    // Load initial data
    loadJobs();
    loadDownloads();
    
    // Start polling for active jobs
    setInterval(pollActiveJobs, 2000);
});

// Handle form submission
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = {
        url: formData.get('url'),
        name: formData.get('name') || null,
        plugin: formData.get('plugin') || null,
        workers: parseInt(formData.get('workers')),
        download_mode: 'server'  // Always server mode
    };
    
    try {
        const response = await fetch(`${API_BASE}/download`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start download');
        }
        
        const job = await response.json();
        activeJobs.add(job.job_id);
        
        // Clear form
        e.target.reset();
        
        // Reload jobs list
        loadJobs();
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

// Load all jobs
async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE}/jobs`);
        const jobs = await response.json();
        
        const jobsList = document.getElementById('jobsList');
        
        if (jobs.length === 0) {
            jobsList.innerHTML = '<p class="empty-state">No active jobs</p>';
            return;
        }
        
        // Clear active jobs and rebuild
        activeJobs.clear();
        
        jobsList.innerHTML = jobs.map(job => {
            // Track active jobs
            if (['pending', 'detecting', 'downloading'].includes(job.status)) {
                activeJobs.add(job.job_id);
            }
            
            return createJobElement(job);
        }).join('');
        
    } catch (error) {
        console.error('Failed to load jobs:', error);
    }
}

// Create job element HTML
function createJobElement(job) {
    const statusClass = `status-${job.status}`;
    const createdAt = new Date(job.created_at).toLocaleString();
    
    let progressHtml = '';
    if (job.progress && job.progress.total > 0) {
        const percent = (job.progress.completed / job.progress.total) * 100;
        progressHtml = `
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${percent}%"></div>
            </div>
            <div>Progress: ${job.progress.completed}/${job.progress.total} tracks (${job.progress.failed} failed)</div>
        `;
    }
    
    let resultHtml = '';
    if (job.result) {
        resultHtml = `
            <div class="job-details">
                <strong>Result:</strong> ${job.result.successful} successful, ${job.result.failed} failed
            </div>
        `;
    }
    
    let actionHtml = '';
    if (job.status === 'completed' || job.status === 'error' || job.status === 'cancelled') {
        // Show Clear button for completed/error/cancelled jobs
        if (job.status === 'completed' && job.result && job.result.successful > 0) {
            const downloadName = job.download_name || job.job_id.substring(0, 8);
            actionHtml = `
                <button class="btn btn-primary btn-small" onclick="downloadAsZip('${downloadName}')">
                    Download ZIP
                </button>
                <button class="btn btn-danger btn-small" onclick="clearJob('${job.job_id}')">
                    Clear
                </button>
            `;
        } else {
            actionHtml = `
                <button class="btn btn-danger btn-small" onclick="clearJob('${job.job_id}')">
                    Clear
                </button>
            `;
        }
    } else {
        // Show Cancel button for active jobs
        actionHtml = `
            <button class="btn btn-danger btn-small" onclick="cancelJob('${job.job_id}')">
                Cancel
            </button>
        `;
    }
    
    return `
        <div class="job-item">
            <div class="job-header">
                <div class="job-title">Job ${job.job_id.substring(0, 8)}</div>
                <span class="job-status ${statusClass}">${job.status}</span>
            </div>
            <div class="job-details">
                <div>Created: ${createdAt}</div>
                ${job.message ? `<div class="job-message">${job.message}</div>` : ''}
                ${progressHtml}
                ${resultHtml}
            </div>
            ${actionHtml}
        </div>
    `;
}

// Poll active jobs for updates
async function pollActiveJobs() {
    if (activeJobs.size === 0) return;
    
    for (const jobId of activeJobs) {
        try {
            const response = await fetch(`${API_BASE}/status/${jobId}`);
            const job = await response.json();
            
            // Update job element
            const jobsList = document.getElementById('jobsList');
            const existingJobs = Array.from(jobsList.children);
            
            // Find and update the specific job
            const jobElement = existingJobs.find(el => 
                el.textContent.includes(jobId.substring(0, 8))
            );
            
            if (jobElement) {
                jobElement.outerHTML = createJobElement(job);
            }
            
            // Remove from active jobs if completed
            if (!['pending', 'detecting', 'downloading'].includes(job.status)) {
                activeJobs.delete(jobId);
                // Reload downloads if job completed successfully
                if (job.status === 'completed') {
                    loadDownloads();
                }
            }
            
        } catch (error) {
            console.error(`Failed to poll job ${jobId}:`, error);
        }
    }
}

// Clear a completed job
async function clearJob(jobId) {
    try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to clear job');
        }
        
        loadJobs();
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

// Cancel an active job
async function cancelJob(jobId) {
    if (!confirm('Cancel this download?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to cancel job');
        }
        
        loadJobs();
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

// State for showing all downloads
let showAllDownloads = false;

// Load completed downloads
async function loadDownloads() {
    try {
        const response = await fetch(`${API_BASE}/downloads`);
        const downloads = await response.json();
        
        const downloadsList = document.getElementById('downloadsList');
        const toggleButton = document.getElementById('toggleDownloads');
        
        if (downloads.length === 0) {
            downloadsList.innerHTML = '<p class="empty-state">No downloads yet</p>';
            toggleButton.style.display = 'none';
            return;
        }
        
        // Show/hide toggle button based on number of downloads
        const INITIAL_SHOW = 5;
        if (downloads.length > INITIAL_SHOW) {
            toggleButton.style.display = 'block';
            toggleButton.textContent = showAllDownloads ? 'Show Less' : `Show All (${downloads.length})`;
        } else {
            toggleButton.style.display = 'none';
        }
        
        // Determine which downloads to show
        const downloadsToShow = showAllDownloads ? downloads : downloads.slice(0, INITIAL_SHOW);
        
        downloadsList.innerHTML = downloadsToShow.map(download => {
            const createdAt = new Date(download.created).toLocaleString();
            const sizeInMB = (download.size / (1024 * 1024)).toFixed(2);
            
            return `
                <div class="download-item">
                    <div class="download-header">
                        <div class="download-title">${download.name}</div>
                    </div>
                    <div class="download-details">
                        <div>Files: ${download.files}</div>
                        <div>Size: ${sizeInMB} MB</div>
                        <div>Created: ${createdAt}</div>
                    </div>
                    <div class="download-actions">
                        <button class="btn btn-primary btn-small" onclick="downloadAsZip('${download.name}')">
                            Download ZIP
                        </button>
                        <button class="btn btn-danger btn-small" onclick="deleteDownload('${download.name}')">
                            Delete
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Failed to load downloads:', error);
    }
}

// Toggle showing all downloads
function toggleAllDownloads() {
    showAllDownloads = !showAllDownloads;
    loadDownloads();
}

// Delete a download
async function deleteDownload(name) {
    if (!confirm(`Delete download "${name}"?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/downloads/${encodeURIComponent(name)}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete download');
        }
        
        loadDownloads();
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

// Download as ZIP
async function downloadAsZip(name) {
    try {
        window.location.href = `${API_BASE}/downloads/${encodeURIComponent(name)}/zip`;
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}