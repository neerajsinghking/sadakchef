// DataTables configuration
document.addEventListener('DOMContentLoaded', function() {
    // Initialize DataTables for all tables with the .data-table class
    const tables = document.querySelectorAll('.data-table');
    tables.forEach(table => {
        new DataTable(table, {
            responsive: true,
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]],
            language: {
                search: "Search:",
                lengthMenu: "Show _MENU_ entries",
                info: "Showing _START_ to _END_ of _TOTAL_ entries",
                infoEmpty: "Showing 0 to 0 of 0 entries",
                infoFiltered: "(filtered from _MAX_ total entries)",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "Next",
                    previous: "Previous"
                }
            }
        });
    });
});
