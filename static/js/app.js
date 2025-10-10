$(document).ready(function() {
    // Load cart from localStorage or initialize as an empty object
    let cart = JSON.parse(localStorage.getItem('buxxelCart')) || {};

    // --- CART FUNCTIONALITY ---

    // 1. Add to Cart (using event delegation on a static parent)
    // This ensures that buttons on newly loaded listings will also work.
    $('#listing-grid').on('click', '.add-to-cart-btn', function() {
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

    // --- PURVEYOR PROFILE MODAL ---
    let purveyorButton = null;
    let originalButtonHtml = '';

    // Use event delegation for the "View Purveyor" button
    $('#listing-grid').on('click', '.view-purveyor-btn', function() {
        purveyorButton = $(this); // The button that was clicked
        const userId = purveyorButton.data('user-id');
        
        // Get a jQuery object for the modal element
        const modalElement = $('#purveyorProfileModal');
        // The modal will be shown via the data-bs-toggle attribute on the button
        // We just need to listen for the 'show' event to populate it.
        
        const contentArea = modalElement.find('#purveyor-profile-content');
        const modalFooter = modalElement.find('.modal-footer');

        // Give the button immediate feedback
        originalButtonHtml = purveyorButton.html();
        purveyorButton.prop('disabled', true).html(
            `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...`
        );

        // 1. Show a loading spinner immediately
        contentArea.html(`
            <div class="text-center p-4">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `);
        modalFooter.hide(); // Hide footer while loading

        // 2. Fetch the profile data from our new API endpoint
        $.ajax({
            url: `/api/profiles/${userId}`,
            type: 'GET',
            success: function(profile) {
                // 3. Populate the modal with the fetched data
                const profileHtml = `
                    <div class="text-center">
                        <i class="bi bi-shop-window fs-1 text-secondary mb-3"></i>
                        <h4 class="mb-1">${profile.username}</h4>
                        <p class="text-muted">Has ${profile.active_listings_count} active listings.</p>
                        <hr>
                        <p>What would you like to do?</p>
                        <a href="/profile/${profile.user_id}" class="btn btn-primary w-100 mb-2">View All Listings by this Purveyor</a>
                        <button class="btn btn-outline-secondary w-100" disabled>Contact Purveyor (Coming Soon)</button>
                    </div>
                `;
                contentArea.html(profileHtml);
                modalFooter.show(); // Show footer again
            },
            error: function() {
                contentArea.html(`<div class="alert alert-danger">Could not load purveyor profile. Please try again later.</div>`);
                modalFooter.show();
            },
            complete: function() {
                // This runs after success or error. Restore the button here.
                if (purveyorButton) {
                    purveyorButton.prop('disabled', false).html(originalButtonHtml);
                    purveyorButton = null;
                }
            }
        });
    });

    // We no longer need the 'hidden.bs.modal' event handler for the button,
    // as the 'complete' callback in the AJAX request now handles it reliably.

    // --- DYNAMIC PAGINATION (INFINITE SCROLL) ---
    const loadMoreContainer = document.getElementById('load-more-container');

    function loadMoreListings(isNewFilter = false) {
        const button = $('#load-more-btn');
        if (button.prop('disabled') && !isNewFilter) return; // Don't load if already loading, unless it's a new filter

        let nextPage;
        if (isNewFilter) {
            $('#listing-grid').empty(); // Clear the grid for new filter results
            nextPage = 1;
            button.data('next-page', 1); // Reset pagination
        } else {
            nextPage = button.data('next-page');
        }

        if (!nextPage) return;

        const originalHtml = button.html();
        button.prop('disabled', true).html(
            `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...`
        );

        // Get current filter state
        const activeTag = $('.tag-btn.active').data('tag') || 'all';
        const searchTerm = $('#search-bar').val();

        $.ajax({
            url: `/api/listings/paged?page=${nextPage}&tag=${activeTag}&search=${encodeURIComponent(searchTerm)}`,
            type: 'GET',
            success: function(response) {
                const listings = response.listings;
                const pagination = response.pagination;

                listings.forEach(listing => {
                    const imageUrl = (listing.image_urls && listing.image_urls.length > 0) 
                        ? listing.image_urls[0] 
                        : 'https://via.placeholder.com/300x200.png?text=No+Image';

                    const imageHtml = `
                        <a href="#" class="image-preview-trigger" data-bs-toggle="modal" data-bs-target="#imagePreviewModal" data-image-url="${imageUrl}">
                            <img src="${imageUrl}" class="card-img-top" alt="${listing.name}">
                        </a>
                    `;

                    const productCardHtml = `
                        <div class="col-lg-3 col-md-4 col-sm-6 listing-card" 
                             data-tags="${(listing.tags || []).join(',')}" 
                             data-name="${listing.name.toLowerCase()}"
                             data-description="${escape(listing.description)}">
                            <div class="card h-100 shadow-sm">
                                ${imageHtml}
                                <div class="card-body d-flex flex-column">
                                    <h5 class="card-title">${listing.name}</h5>
                                    <p class="card-text fw-bold fs-5 mb-3">$${listing.price.toFixed(2)}</p>
                                    <div class="mt-auto">
                                        <button class="btn btn-warning w-100 mb-2 add-to-cart-btn"
                                                data-id="${listing.id}"
                                                data-name="${listing.name}"
                                                data-price="${listing.price}">
                                            Add to Cart
                                        </button>
                                        <button class="btn btn-outline-secondary w-100 view-purveyor-btn"
                                                data-bs-toggle="modal"
                                                data-bs-target="#purveyorProfileModal"
                                                data-user-id="${listing.user_id}">
                                            View Purveyor</button>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                    $('#listing-grid').append(productCardHtml);
                });

                // If it was a new filter and no results came back, show a message.
                if (isNewFilter && listings.length === 0) {
                    $('#listing-grid').html('<div class="text-center p-5 col-12"><h4 class="text-muted">No listings match your filters.</h4></div>');
                }

                if (pagination.has_next) {
                    button.data('next-page', pagination.page + 1);
                    button.prop('disabled', false).html(originalHtml);
                } else {
                    button.hide();
                    if (observer) {
                        observer.disconnect(); // Stop observing if no more pages
                    }
                }
            },
            error: function() {
                button.prop('disabled', false).html('Failed to load. Try again?');
            }
        });
    }

    const loadMoreBtn = document.getElementById('load-more-btn');
    if (loadMoreContainer && loadMoreBtn) {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                loadMoreListings(false); // isNewFilter = false
            }
        }, { threshold: 1.0 }); // Trigger when 100% of the element is visible

        // Start observing the button
        observer.observe(loadMoreContainer);
        // And trigger the first load immediately if the button is present on the page
        loadMoreListings(true);
    }

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
    $('#popular-tags-container').on('click', '.tag-btn', function() {
        const tag = $(this).data('tag');

        // Active button style
        $('.tag-btn').removeClass('active');
        $(this).addClass('active');

        // Instead of hiding/showing, fetch new filtered data
        loadMoreListings(true); // isNewFilter = true
    });

    // 2. Search Bar Filter
    $('#search-bar').on('keyup', debounce(function() {
        // Fetch new filtered data
        loadMoreListings(true); // isNewFilter = true
    }, 300)); // 300ms delay

    // --- AUTH FUNCTIONALITY ---

    // Signup Form Submission
    $('#signupForm').on('submit', async function(event) { // Make the handler async
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

        submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Signing Up...');

        const { data, error } = await window.supabaseClient.auth.signUp({ email, password });

        if (error) {
            alertDiv.text(error.message).removeClass('alert-success').addClass('alert-danger').show();
        } else {
            alertDiv.text('Signup successful! Please check your email to verify your account.').removeClass('alert-danger').addClass('alert-success').show();
            // Reset form and close modal after a short delay
            setTimeout(() => {
                $('#authModal').modal('hide');
                $('#signupForm')[0].reset();
                alertDiv.hide().text('');
            }, 4000);
        }
        submitBtn.prop('disabled', false).html(originalBtnHtml);
    });

    // Login Form Submission
    $('#loginForm').on('submit', async function(event) { // Make the handler async
        event.preventDefault();

        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        const originalBtnHtml = submitBtn.html();
        const alertDiv = $('#login-alert');
        const email = $('#loginIdentifier').val();
        const password = $('#loginPassword').val();

        submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Logging In...');

        const { data, error } = await window.supabaseClient.auth.signInWithPassword({ email, password });

        if (error) {
            alertDiv.text(error.message).removeClass('alert-success').addClass('alert-danger').show();
            submitBtn.prop('disabled', false).html(originalBtnHtml);
        } else {
            // The login was successful, simply reload the page.
            // The updateAuthState function will handle the UI changes on page load.
            location.reload();
        }
    });

    // --- Password Reset Flow ---

    // 1. Show password reset form
    $('#forgot-password-link').on('click', function(e) {
        e.preventDefault();
        $('#loginForm, #signup-view, hr.my-4').hide();
        $('#password-reset-view').show();
        $('#authModalLabel').text('Reset Password');
    });

    // 2. Go back to login from password reset
    $('#back-to-login-link').on('click', function(e) {
        e.preventDefault();
        $('#password-reset-view').hide();
        $('#loginForm, #signup-view, hr.my-4').show();
        $('#authModalLabel').text('Login or Create an Account');
    });

    // 3. Handle the reset request form submission
    $('#resetPasswordRequestForm').on('submit', async function(e) {
        e.preventDefault();
        const email = $('#resetEmail').val();
        const alertDiv = $('#reset-request-alert');
        const submitBtn = $(this).find('button[type="submit"]');
        const originalBtnHtml = submitBtn.html();

        submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Sending...');

        const { error } = await window.supabaseClient.auth.resetPasswordForEmail(email, {
            redirectTo: `${window.location.origin}/reset-password`,
        });

        if (error) {
            alertDiv.text(error.message).removeClass('alert-success').addClass('alert-danger').show();
        } else {
            alertDiv.text('Password reset link sent! Please check your email.').removeClass('alert-danger').addClass('alert-success').show();
        }
        submitBtn.prop('disabled', false).html(originalBtnHtml);
    });


    // --- DYNAMIC AUTH STATE IN NAVBAR ---

    async function updateAuthState() {
        // Use the reliable getSession method to check auth state
        const { data, error } = await window.supabaseClient.auth.getSession();
        if (error) {
            console.error("Error getting session:", error);
            return;
        }
        const session = data.session;
        const guestCtaSection = $('#guest-cta-section');

        if (session && session.user) {
            // User is logged in
            $('#auth-guest').addClass('d-none');
            $('#auth-user').removeClass('d-none').addClass('d-flex');
            $('#user-email').text(session.user.email);
            // The guest CTA should be hidden for logged-in users
            guestCtaSection.hide();
        } else {
            // User is a guest
            $('#auth-guest').removeClass('d-none').addClass('d-flex');
            $('#auth-user').addClass('d-none');
            guestCtaSection.show(); // Show the CTA for guests

            // CTA button on homepage should open the signup modal
            $('#create-listing-cta').attr('href', '#').on('click', function(e) {
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

    // Logout Button Handler
    $('#logout-btn').on('click', async function() {
        const { error } = await window.supabaseClient.auth.signOut();
        if (error) {
            console.error('Error logging out:', error);
            alert('Failed to log out. Please try again.');
        } else {
            // Show a quick feedback message (optional)
            alert('You have been logged out.');
            // Reload the page to reflect the new state
            location.reload();
        }
    });

    // When the auth modal is closed, hide the contextual message so it doesn't show up next time
    $('#authModal').on('hidden.bs.modal', function () {
        $('#auth-context-message').hide().text('');
        // Also reset the password form view
        $('#password-reset-view').hide();
        $('#loginForm, #signup-view, hr.my-4').show();
        $('#authModalLabel').text('Login or Create an Account');
        $('#reset-request-alert').hide().text('');
    });

    // --- POPULAR TAGS ---
    function loadPopularTags() {
        const container = $('#popular-tags-container');
        if (!container.length) return;

        $.ajax({
            url: '/api/tags/popular',
            type: 'GET',
            success: function(tags) {
                // Always add an "All" button first
                container.append('<button class="btn btn-secondary tag-btn active" data-tag="all">All</button>');
                tags.forEach(tagInfo => {
                    const tagButton = `<button class="btn btn-outline-secondary tag-btn" data-tag="${tagInfo.tag}">${tagInfo.tag}</button>`;
                    container.append(tagButton);
                });
            },
            error: function() {
                container.html('<span class="text-danger">Could not load popular tags.</span>');
            }
        });
    }

    // --- GEOLOCATION ---
    function loadUserLocation() {
        const locationDisplay = $('#location-display');
        if (!locationDisplay.length) return;

        // Use a free IP-based geolocation service
        $.ajax({
            url: 'http://ip-api.com/json',
            type: 'GET',
            success: function(response) {
                if (response && response.status === 'success' && response.city) {
                    const locationText = `Delivering to: ${response.city}, ${response.countryCode}`;
                    locationDisplay.text(locationText).removeClass('d-none');
                }
            },
            error: function() {
                // Silently fail if the API call doesn't work. No need to show an error.
                console.log("Could not retrieve user location via IP.");
            }
        });
    }

    // Initial cart update on page load
    updateCart();
    // Check and update the auth state on page load
    updateAuthState();
    // Load popular tags on the homepage
    loadPopularTags();
    // Load user's general location
    loadUserLocation();

    // --- IMAGE PREVIEW MODAL HANDLER ---
    // Use event delegation on the body to catch clicks from any listing card on any page
    $('body').on('click', '.image-preview-trigger', function(e) {
        e.preventDefault();
        const imageUrl = $(this).data('image-url');
        // Find the parent listing card and get its description data
        const description = unescape($(this).closest('.listing-card').data('description') || '');

        if (imageUrl) {
            $('#imagePreviewSrc').attr('src', imageUrl);
        }
        // Set the description text in the modal footer
        $('#imagePreviewDescription').text(description);
    });
});