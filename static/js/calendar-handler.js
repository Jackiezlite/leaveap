// Calendar and date handling functionality
$(document).ready(function() {
    let startDate = null;
    let endDate = null;
    let selectedDates = new Map();  // For advanced mode
    let selecting = false;  // Flag to prevent recursive selection

    // Initialize Simple Mode Calendar
    let simpleCalendar = new FullCalendar.Calendar(document.getElementById('simpleCalendar'), {
        initialView: 'dayGridMonth',
        selectable: true,
        selectMinDistance: 5,  // Make it easier to select a range
        unselectAuto: false,   // Don't unselect when clicking outside
        selectionMinDistance: 0, // Allow selecting by clicking
        selectOverlap: true,   // Allow selecting over events
        selectConstraint: {
            start: new Date(),  // Can't select dates before today
        },
        select: function(info) {
            // Disable drag selection, we'll use dateClick instead
            simpleCalendar.unselect();
        },
        dateClick: function(info) {
            const clickedDate = info.date;
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            
            // Don't allow selecting dates in the past
            if (clickedDate < today) {
                return;
            }
            
            if (!startDate || (startDate && endDate)) {
                // First click - set start date
                startDate = clickedDate;
                endDate = null;
                $('#simpleEndDateInput').val('');
                $('#simpleDateInput').val(startDate.toISOString().split('T')[0]);
                updateDateDisplay(startDate, null);
                highlightRange();
                // Show message to select end date
                $('#simpleEndDateDisplay').html(`
                    <span class="text-muted small">
                        <i class="fas fa-calendar"></i> Now select end date
                    </span>
                `);
            } else {
                // Second click - set end date
                if (clickedDate < startDate) {
                    // If clicked before start date, swap them
                    endDate = startDate;
                    startDate = clickedDate;
                } else {
                    endDate = clickedDate;
                }
                $('#simpleDateInput').val(startDate.toISOString().split('T')[0]);
                $('#simpleEndDateInput').val(endDate.toISOString().split('T')[0]);
                updateDateDisplay(startDate, endDate);
                highlightRange();
            }
            validateForm();
        },
        eventDidMount: function(info) {
            // Style the selection events
            if (info.event.display === 'background') {
                info.el.style.backgroundColor = '#e3f2fd';
                info.el.style.opacity = '0.7';
            }
        },
        validRange: function(nowDate) {
            return { start: nowDate };
        },
        headerToolbar: {
            left: 'title',
            right: 'prev,next today'
        }
    });

    // Function to highlight the selected date range
    function highlightRange() {
        selecting = true;
        simpleCalendar.removeAllEvents();
        
        if (startDate) {
            // Add background event for start date
            simpleCalendar.addEvent({
                start: startDate,
                end: new Date(startDate.getTime() + 24*60*60*1000),
                display: 'background',
                className: 'selected-start'
            });

            if (endDate) {
                // Add background event for the range
                simpleCalendar.addEvent({
                    start: startDate,
                    end: new Date(endDate.getTime() + 24*60*60*1000),
                    display: 'background',
                    className: 'selected-range'
                });
            }
        }
        
        selecting = false;
    }

    // Initialize Advanced Mode Calendar
    let advancedCalendar = new FullCalendar.Calendar(document.getElementById('advancedCalendar'), {
        initialView: 'dayGridMonth',
        selectable: true,
        dateClick: function(info) {
            const dateStr = info.dateStr;
            if (!selectedDates.has(dateStr)) {
                selectedDates.set(dateStr, true);
                updateSelectedDatesDisplay();
                validateForm();
            }
        },
        validRange: function(nowDate) {
            return { start: nowDate };
        },
        eventDidMount: function(info) {
            if (info.event.display === 'background') {
                info.el.style.backgroundColor = '#e3f2fd';
                info.el.style.opacity = '0.7';
            }
        },
        headerToolbar: {
            left: 'title',
            right: 'prev,next today'
        }
    });

    // Render both calendars
    simpleCalendar.render();
    advancedCalendar.render();

    // Mode Switch Handler
    $('#modeSwitch').change(function() {
        const isAdvanced = $(this).prop('checked');
        $('#simple-mode').toggle(!isAdvanced);
        $('#advanced-mode').toggle(isAdvanced);
        
        // Reset the other mode
        if (isAdvanced) {
            clearDateSelection();
        } else {
            selectedDates.clear();
            updateSelectedDatesDisplay();
        }
        validateForm();
    });

    // Function to update the date display
    function updateDateDisplay(start, end = null) {
        const formatOptions = { 
            weekday: 'short', 
            month: 'short', 
            day: 'numeric',
            year: 'numeric' 
        };

        if (start) {
            const startStr = start.toLocaleDateString('en-US', formatOptions);
            $('#simpleDateInput').val(start.toISOString().split('T')[0]);
            $('#simpleDateDisplay').html(`
                <span class="text-success">
                    <i class="fas fa-calendar-check"></i> ${startStr}
                </span>
            `);
        } else {
            $('#simpleDateInput').val('');
            $('#simpleDateDisplay').html(`
                <span class="text-muted small">
                    <i class="fas fa-calendar"></i> Select start date
                </span>
            `);
        }

        if (end) {
            const endStr = end.toLocaleDateString('en-US', formatOptions);
            $('#simpleEndDateInput').val(end.toISOString().split('T')[0]);
            $('#simpleEndDateDisplay').html(`
                <span class="text-danger">
                    <i class="fas fa-calendar-check"></i> ${endStr}
                </span>
            `);

            // Calculate duration
            const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1;
            $('#simpleDuration').val(days);
            $('#simpleDurationDisplay span').text(days);
            $('#simpleDurationDisplay').removeClass('alert-light').addClass('alert-primary');
        } else {
            $('#simpleEndDateInput').val('');
            $('#simpleEndDateDisplay').html(`
                <span class="text-muted small">
                    <i class="fas fa-calendar"></i> Select end date
                </span>
            `);
            $('#simpleDurationDisplay span').text('0');
            $('#simpleDurationDisplay').removeClass('alert-primary').addClass('alert-light');
        }
    }

    // Clear date selection
    function clearDateSelection() {
        startDate = null;
        endDate = null;
        updateDateDisplay(null, null);
        simpleCalendar.removeAllEvents();
        simpleCalendar.unselect();
    }

    // Clear button handler
    $('#clearDates').click(clearDateSelection);

    // Update Selected Dates Display for advanced mode
    function updateSelectedDatesDisplay() {
        const datesList = [...selectedDates.keys()].sort();
        $('#dates').val(datesList.join(';'));  // Updated to match the backend
        
        const mainList = $('#selectedDatesList');
        mainList.empty();
        
        if (datesList.length > 0) {
            datesList.forEach(date => {
                mainList.append(`
                    <div class="list-group-item">
                        ${date}
                        <button type="button" class="btn-close" onclick="removeDate('${date}')"></button>
                    </div>
                `);
            });
            $('#noDateSelectedMessage').hide();
        } else {
            $('#noDateSelectedMessage').show();
        }
    }

    // Form validation
    function validateForm() {
        const leaveType = $('#leaveType').val();
        const isAdvanced = $('#modeSwitch').prop('checked');
        const hasValidDates = isAdvanced ? selectedDates.size > 0 : (startDate && endDate);
        
        $('button[type="submit"]').prop('disabled', !leaveType || !hasValidDates);
    }

    // Make removeDate function global for the onclick handler
    window.removeDate = function(date) {
        selectedDates.delete(date);
        updateSelectedDatesDisplay();
        validateForm();
    };
});

    $('#leaveType').change(validateForm);
    $('[name="notes"]').on('input', validateForm);
    $('#simpleDuration').on('input', validateForm);

    // Initial validation
    validateForm();
;