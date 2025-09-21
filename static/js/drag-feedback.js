// Add visual feedback for drag operations
document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('simpleCalendar');
    if (!calendarEl) return;

    let isDragging = false;
    
    // Add mousedown listener to start drag
    calendarEl.addEventListener('mousedown', function(e) {
        const dayEl = e.target.closest('.fc-day');
        if (dayEl) {
            isDragging = true;
            dayEl.classList.add('selecting');
        }
    });

    // Add mousemove listener for drag feedback
    calendarEl.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        
        const dayEl = e.target.closest('.fc-day');
        if (dayEl) {
            // Remove selecting class from all days
            calendarEl.querySelectorAll('.fc-day').forEach(el => {
                if (el !== dayEl) el.classList.remove('selecting');
            });
            dayEl.classList.add('selecting');
        }
    });

    // Add mouseup listener to end drag
    document.addEventListener('mouseup', function() {
        if (!isDragging) return;
        isDragging = false;
        
        // Remove selecting class from all days
        calendarEl.querySelectorAll('.fc-day').forEach(el => {
            el.classList.remove('selecting');
        });
    });

    // Add tooltip to show drag instructions
    const fcDays = calendarEl.querySelectorAll('.fc-day:not(.fc-day-other)');
    fcDays.forEach(day => {
        $(day).tooltip({
            title: 'Click to select a single date, or click and drag to select a range',
            placement: 'top',
            trigger: 'hover',
            container: 'body'
        });
    });
});