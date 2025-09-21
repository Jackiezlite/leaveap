// File Preview Functionality
function createFilePreview(file) {
    const reader = new FileReader();
    const previewContainer = document.getElementById('attachmentPreview');
    previewContainer.innerHTML = '<div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    
    reader.onload = function(e) {
        const ext = file.name.split('.').pop().toLowerCase();
        const isImage = ['png', 'jpg', 'jpeg', 'gif', 'bmp'].includes(ext);
        
        let previewHTML = '';
        if (isImage) {
            previewHTML = `
                <div class="card mt-2">
                    <img src="${e.target.result}" class="img-fluid" style="max-height: 200px; object-fit: contain;">
                    <div class="card-body p-2">
                        <small class="text-muted">${file.name} (${(file.size/1024).toFixed(1)} KB)</small>
                    </div>
                </div>
            `;
        } else if (ext === 'pdf') {
            previewHTML = `
                <div class="card mt-2">
                    <div class="card-body p-2">
                        <i class="fas fa-file-pdf text-danger fa-2x"></i>
                        <span class="ms-2">${file.name}</span>
                        <br>
                        <small class="text-muted">${(file.size/1024).toFixed(1)} KB</small>
                    </div>
                </div>
            `;
        }
        
        previewContainer.innerHTML = previewHTML;
    };
    
    reader.onerror = function() {
        previewContainer.innerHTML = '<div class="alert alert-danger">Error loading file preview</div>';
    };
    
    if (file.type.startsWith('image/')) {
        reader.readAsDataURL(file);
    } else {
        reader.readAsArrayBuffer(file);
    }
}

// Clear attachment
document.getElementById('clearAttachment').addEventListener('click', function() {
    document.getElementById('attachmentInput').value = '';
    document.getElementById('attachmentPreview').innerHTML = '';
});

// Date Range Handling
let startDate = null;
let endDate = null;

function updateDateRange(selectedDate) {
    if (!startDate || (startDate && endDate)) {
        // Start new selection
        startDate = selectedDate;
        endDate = null;
        document.getElementById('simpleDateInput').value = startDate;
        document.getElementById('simpleEndDateInput').value = '';
        document.getElementById('simpleDateDisplay').textContent = formatDate(startDate);
        document.getElementById('simpleEndDateDisplay').textContent = 'Select end date';
        document.getElementById('simpleDurationDisplay').querySelector('span').textContent = '1';
    } else {
        // Complete the range
        const start = new Date(startDate);
        const end = new Date(selectedDate);
        
        if (end < start) {
            // Swap if end is before start
            endDate = startDate;
            startDate = selectedDate;
        } else {
            endDate = selectedDate;
        }
        
        document.getElementById('simpleDateInput').value = startDate;
        document.getElementById('simpleEndDateInput').value = endDate;
        document.getElementById('simpleDateDisplay').textContent = formatDate(startDate);
        document.getElementById('simpleEndDateDisplay').textContent = formatDate(endDate);
        
        // Calculate duration
        const days = Math.ceil((new Date(endDate) - new Date(startDate)) / (1000 * 60 * 60 * 24)) + 1;
        document.getElementById('simpleDuration').value = days;
        document.getElementById('simpleDurationDisplay').querySelector('span').textContent = days;
    }
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        weekday: 'short', 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}

// Leave Type Validation
function validateLeaveType() {
    const leaveType = document.getElementById('leaveType').value;
    const submitBtn = document.querySelector('button[type="submit"]');
    const notesInput = document.querySelector('[name="notes"]');
    
    if (leaveType) {
        submitBtn.disabled = false;
        notesInput.disabled = false;
    } else {
        submitBtn.disabled = true;
        notesInput.disabled = true;
    }
}

// Form Validation
function validateForm(event) {
    const form = event.target;
    const leaveType = form.querySelector('#leaveType').value;
    const isAdvancedMode = document.getElementById('modeSwitch').checked;
    const notes = form.querySelector('[name="notes"]').value.trim();
    
    if (!leaveType) {
        alert('Please select a leave type');
        event.preventDefault();
        return false;
    }
    
    if (isAdvancedMode) {
        const selectedDates = document.getElementById('datesList').value;
        if (!selectedDates) {
            alert('Please select at least one date in advanced mode');
            event.preventDefault();
            return false;
        }
    } else {
        const simpleDate = document.getElementById('simpleDatePicker').value;
        if (!simpleDate) {
            alert('Please select a date');
            event.preventDefault();
            return false;
        }
    }
    
    if (!notes) {
        alert('Please enter a reason for your leave');
        event.preventDefault();
        return false;
    }
    
    return true;
}

// Initialize form handlers
document.addEventListener('DOMContentLoaded', function() {
    // File input handler
    document.getElementById('attachmentInput').addEventListener('change', function(e) {
        if (this.files && this.files[0]) {
            const file = this.files[0];
            const ext = file.name.split('.').pop().toLowerCase();
            
            // Validate file type
            if (!['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp'].includes('.' + ext)) {
                alert('Invalid file type. Please upload a PDF or image file.');
                this.value = '';
                return;
            }
            
            // Validate file size (max 10MB)
            if (file.size > 10 * 1024 * 1024) {
                alert('File is too large. Maximum size is 10MB.');
                this.value = '';
                return;
            }
            
            createFilePreview(file);
        }
    });
    
    // Duration validation
    document.getElementById('simpleDuration').addEventListener('change', function() {
        validateDuration(this);
    });
    
    // Leave type validation
    document.getElementById('leaveType').addEventListener('change', validateLeaveType);
    
    // Form validation
    document.getElementById('leaveForm').addEventListener('submit', validateForm);
    
    // Mode switching
    const modeSwitch = document.getElementById('modeSwitch');
    if (modeSwitch) {
        modeSwitch.addEventListener('change', function() {
            const simpleMode = document.getElementById('simple-mode');
            const advancedMode = document.getElementById('advanced-mode');
            const simpleCalendar = document.querySelector('#simpleCalendar .fc');
            const advancedCalendar = document.querySelector('#advancedCalendar .fc');
            
            if (this.checked) {
                simpleMode.style.display = 'none';
                advancedMode.style.display = 'block';
                // Re-render advanced calendar if needed
                if (advancedCalendar) {
                    advancedCalendar.dispatchEvent(new Event('resize'));
                }
            } else {
                advancedMode.style.display = 'none';
                simpleMode.style.display = 'block';
                // Re-render simple calendar if needed
                if (simpleCalendar) {
                    simpleCalendar.dispatchEvent(new Event('resize'));
                }
            }
        });
    }
    
    // Initial state
    validateLeaveType();
});