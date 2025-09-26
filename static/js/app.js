$(document).ready(function() {
    // Load cart from localStorage or initialize as an empty object
    let cart = JSON.parse(localStorage.getItem('buxxelCart')) || {};

    // --- CART FUNCTIONALITY ---

    // 1. Add to Cart
    $('.add-to-cart-btn').on('click', function() {
        const button = $(this);
        const id = button.data('id');
        const name = button.data('name');
        const price = parseFloat(button.data('price'));

        if (cart[id]) {
            cart[id].quantity++;
        } else {
            cart[id] = { name: name, price: price, quantity: 1 };
        }

        updateCart();
        saveCart();

        // Visual feedback
        button.text('Added!').addClass('btn-success').removeClass('btn-warning');
        setTimeout(() => {
            button.text('Add to Cart').removeClass('btn-success').addClass('btn-warning');
        }, 1000);
    });

    // 2. Update Cart Count and Modal
    function updateCart() {
        let totalItems = 0;
        let totalPrice = 0;
        const cartItemsContainer = $('#cart-items-container');
        cartItemsContainer.empty();

        if (Object.keys(cart).length === 0) {
            cartItemsContainer.html('<p>Your cart is empty.</p>');
        } else {
            const itemList = $('<ul class="list-group"></ul>');
            for (const id in cart) {
                const item = cart[id];
                totalItems += item.quantity;
                totalPrice += item.price * item.quantity;

                const itemHtml = `
                    <li class="list-group-item d-flex justify-content-between align-items-center" data-id="${id}">
                        <div>
                            <h6 class="my-0">${item.name}</h6>
                            <small class="text-muted">Price: $${item.price.toFixed(2)}</small>
                        </div>
                        <div class="d-flex align-items-center">
                            <button class="btn btn-sm btn-outline-secondary decrease-qty" data-id="${id}">-</button>
                            <span class="mx-2 cart-item-quantity">${item.quantity}</span>
                            <button class="btn btn-sm btn-outline-secondary increase-qty" data-id="${id}">+</button>
                            <button class="btn btn-sm btn-danger ms-3 remove-item" data-id="${id}" aria-label="Remove item">&times;</button>
                        </div>
                    </li>
                `;
                itemList.append(itemHtml);
            }
            cartItemsContainer.append(itemList);
        }

        $('#cart-count').text(totalItems);
        $('#cart-total').text(totalPrice.toFixed(2));
    }

    // 3. Save Cart to Local Storage
    function saveCart() {
        localStorage.setItem('buxxelCart', JSON.stringify(cart));
    }

    // 4. Cart Item Management (Increase, Decrease, Remove)
    $('#cart-items-container').on('click', '.increase-qty', function() {
        const id = $(this).data('id');
        if (cart[id]) {
            cart[id].quantity++;
            updateCart();
            saveCart();
        }
    });

    $('#cart-items-container').on('click', '.decrease-qty', function() {
        const id = $(this).data('id');
        if (cart[id]) {
            cart[id].quantity--;
            if (cart[id].quantity <= 0) {
                delete cart[id];
            }
            updateCart();
            saveCart();
        }
    });

    $('#cart-items-container').on('click', '.remove-item', function() {
        const id = $(this).data('id');
        if (cart[id]) {
            delete cart[id];
            updateCart();
            saveCart();
        }
    });

    // --- UTILITY FUNCTIONS ---

    // Debounce function to limit the rate at which a function gets called.
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // --- FILTERING FUNCTIONALITY ---

    // 1. Category Filter
    $('.category-btn').on('click', function() {
        const category = $(this).data('category');

        // Active button style
        $('.category-btn').removeClass('active');
        $(this).addClass('active');

        if (category === 'all') {
            $('.listing-card').show();
        } else {
            $('.listing-card').hide();
            $(`.listing-card[data-category="${category}"]`).show();
        }
        // Reset search bar when changing category
        $('#search-bar').val('');
    });

    // 2. Search Bar Filter
    $('#search-bar').on('keyup', debounce(function() {
        const searchTerm = $(this).val().toLowerCase();
        const activeCategory = $('.category-btn.active').data('category');

        $('.listing-card').each(function() {
            const card = $(this);
            const listingName = card.data('name').toLowerCase();
            const listingCategory = card.data('category');

            const isNameMatch = listingName.includes(searchTerm);
            const isCategoryMatch = (activeCategory === 'all' || listingCategory === activeCategory);

            if (isNameMatch && isCategoryMatch) {
                card.show();
            } else {
                card.hide();
            }
        });
    }, 300)); // 300ms delay

    // --- AUTH FUNCTIONALITY ---

    // Signup Form Submission
    $('#signupForm').on('submit', function(event) {
        event.preventDefault();

        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        const originalBtnHtml = submitBtn.html();

        const alertDiv = $('#signup-alert');
        const email = $('#signupEmail').val();
        const password = $('#signupPassword').val();
        const confirmPassword = $('#confirmPassword').val();


        // Basic client-side validation
        if (password !== confirmPassword) {
            alertDiv.text('Passwords do not match.').removeClass('alert-success').addClass('alert-danger').show();
            return;
        }

        $.ajax({
            beforeSend: function() {
                submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Signing Up...');
            },
            url: '/signup',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ email, password }),
            success: function(response) {
                alertDiv.text(response.message).removeClass('alert-danger').addClass('alert-success').show();
                // Reset form and close modal after a short delay
                setTimeout(() => {
                    $('#signupModal').modal('hide');
                    $('#signupForm')[0].reset();
                    alertDiv.hide().text('');
                }, 3000);
            },
            error: function(xhr) {
                const errorMsg = xhr.responseJSON ? xhr.responseJSON.error : 'An unknown error occurred during signup.';
                alertDiv.text(errorMsg).removeClass('alert-success').addClass('alert-danger').show();
            },
            complete: function() {
                submitBtn.prop('disabled', false).html(originalBtnHtml);
            }
        });
    });

    // Login Form Submission
    $('#loginForm').on('submit', function(event) {
        event.preventDefault();

        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        const originalBtnHtml = submitBtn.html();
        const alertDiv = $('#login-alert');
        // The backend expects an email for password-based login.
        const email = $('#loginIdentifier').val();
        const password = $('#loginPassword').val();

        $.ajax({
            beforeSend: function() {
                submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Logging In...');
            },
            url: '/login',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ email: email, password: password }),
            success: function(response) {
                alertDiv.text('Login successful! Reloading...').removeClass('alert-danger').addClass('alert-success').show();
                
                // Store session data in localStorage to persist login state
                localStorage.setItem('supabaseSession', JSON.stringify(response));

                // Reload the page to reflect the logged-in state after a short delay
                setTimeout(() => {
                    location.reload();
                }, 1500);
            },
            error: function(xhr) {
                const errorMsg = xhr.responseJSON ? xhr.responseJSON.error : 'An unknown error occurred during login.';
                alertDiv.text(errorMsg).removeClass('alert-success').addClass('alert-danger').show();
            },
            complete: function(xhr, textStatus) {
                // Only restore the button if the request failed. On success, the page reloads.
                if (textStatus !== 'success') {
                    submitBtn.prop('disabled', false).html(originalBtnHtml);
                }
            }
        });
    });

    // --- DYNAMIC AUTH STATE IN NAVBAR ---

    function updateAuthState() {
        const session = JSON.parse(localStorage.getItem('supabaseSession'));
        const createListingBtn = $('#create-listing-cta');

        if (session && session.user) {
            // User is logged in
            $('#auth-guest').addClass('d-none');
            $('#auth-user').removeClass('d-none').addClass('d-flex');
            $('#user-email').text(session.user.email);

            // CTA button on homepage should link to the create page
            if (createListingBtn.length) {
                createListingBtn.attr('href', '/new-listing').off('click');
            }
        } else {
            // User is a guest
            $('#auth-guest').removeClass('d-none').addClass('d-flex');
            $('#auth-user').addClass('d-none');

            // CTA button on homepage should open the signup modal
            if (createListingBtn.length) {
                createListingBtn.attr('href', '#').on('click', function(e) {
                    e.preventDefault();
                    // Add the contextual message before showing the modal
                    $('#auth-context-message')
                        .text('You must log in or sign up to create a listing.')
                        .show();
                    const authModal = new bootstrap.Modal(document.getElementById('authModal'));
                    authModal.show();
                });
            }
        }
    }

    // Logout Button Handler
    $('#logout-btn').on('click', function() {
        // Simply remove the session from local storage
        localStorage.removeItem('supabaseSession');
        
        // Show a quick feedback message (optional)
        alert('You have been logged out.');

        // Reload the page to reflect the new state
        location.reload();
    });

    // When the auth modal is closed, hide the contextual message so it doesn't show up next time
    $('#authModal').on('hidden.bs.modal', function () {
        $('#auth-context-message').hide().text('');
    });

    // Initial cart update on page load
    updateCart();
    // Check and update the auth state on page load
    updateAuthState();
});