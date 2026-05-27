const socket = io();
const searchInput = document.getElementById('search');
const chatList = document.getElementById('chatList');
const messagesDiv = document.getElementById('messages');
const messageForm = document.getElementById('messageForm');
const messageInput = document.getElementById('messageInput');
const fileInput = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const previewImage = document.getElementById('previewImage');
const previewFileName = document.getElementById('previewFileName');
const clearFile = document.getElementById('clearFile');
const chatHeader = document.getElementById('chatHeader');
const forwardModal = document.getElementById('forwardModal');
const forwardSearch = document.getElementById('forwardSearch');
const forwardUserList = document.getElementById('forwardUserList');
const cancelForward = document.getElementById('cancelForward');
const sendForward = document.getElementById('sendForward');
const createGroupBtn = document.getElementById('createGroupBtn');
const groupModal = document.getElementById('groupModal');
const groupNameInput = document.getElementById('groupName');
const groupSearch = document.getElementById('groupSearch');
const groupUserList = document.getElementById('groupUserList');
const cancelGroup = document.getElementById('cancelGroup');
const createGroup = document.getElementById('createGroup');
const participantsModal = document.getElementById('participantsModal');
const participantsList = document.getElementById('participantsList');
const addParticipantBtn = document.getElementById('addParticipantBtn');
const addParticipantSearch = document.getElementById('addParticipantSearch');
const addParticipantList = document.getElementById('addParticipantList');
const adminOnlyToggleContainer = document.getElementById('adminOnlyToggleContainer');
const adminOnlyToggle = document.getElementById('adminOnlyToggle');
const closeParticipants = document.getElementById('closeParticipants');
const replyPreview = document.getElementById('replyPreview');
const replyMessage = document.getElementById('replyMessage');
const clearReply = document.getElementById('clearReply');
const profileLink = document.getElementById('profileLink');
const profileEditModal = document.getElementById('profileEditModal');
const profileForm = document.getElementById('profileForm');
const profileFullName = document.getElementById('profileFullName');
const profilePosition = document.getElementById('profilePosition');
const profileDepartment = document.getElementById('profileDepartment');
const profileEmail = document.getElementById('profileEmail');
const profilePhone = document.getElementById('profilePhone');
const profileAvatarInput = document.getElementById('profileAvatarInput');
const profileAvatarPreview = document.getElementById('profileAvatarPreview');
const cancelProfileEdit = document.getElementById('cancelProfileEdit');
const saveProfile = document.getElementById('saveProfile');
const profileViewModal = document.getElementById('profileViewModal');
const profileViewAvatar = document.getElementById('profileViewAvatar');
const profileViewUsername = document.getElementById('profileViewUsername');
const profileViewFullName = document.getElementById('profileViewFullName');
const profileViewPosition = document.getElementById('profileViewPosition');
const profileViewDepartment = document.getElementById('profileViewDepartment');
const profileViewEmail = document.getElementById('profileViewEmail');
const profileViewPhone = document.getElementById('profileViewPhone');
const closeProfileView = document.getElementById('closeProfileView');
const logoutBtn = document.getElementById('logoutBtn');
const emojiBtn = document.getElementById('emojiBtn');
const emojiModal = document.getElementById('emojiModal');
const emojiGrid = document.getElementById('emojiGrid');
const closeEmojiModal = document.getElementById('closeEmojiModal');
const stickerBtn = document.getElementById('stickerBtn');
const stickerModal = document.getElementById('stickerModal');
const stickerInput = document.getElementById('stickerInput');
const closeStickerModal = document.getElementById('closeStickerModal');
const userStickersTab = document.getElementById('userStickersTab');
const commonStickersTab = document.getElementById('commonStickersTab');
const stickerGrid = document.getElementById('stickerGrid');

let currentRecipient = null;
let currentGroupId = null;
let messageToForward = null;
let selectedForwardUsers = [];
let selectedGroupMembers = [];
let replyToMessage = null;
let lastChatList = [];
let currentStickerTab = 'user';
let isLoadingMessages = false;

if (typeof currentUser === 'undefined') {
    console.error('Current user not defined');
    window.location.href = '/';
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

const refreshChats = debounce(() => {
    socket.emit('get_chats');
}, 500);

setInterval(() => {
    socket.emit('heartbeat');
}, 30000);

// Emoji Modal Handlers
emojiBtn.addEventListener('click', () => {
    emojiModal.classList.add('show');
});

closeEmojiModal.addEventListener('click', () => {
    emojiModal.classList.remove('show');
});

emojiGrid.addEventListener('click', (e) => {
    if (e.target.classList.contains('emoji')) {
        messageInput.value += e.target.textContent;
        messageInput.focus();
    }
});

// Sticker Modal Handlers
stickerBtn.addEventListener('click', () => {
    stickerModal.classList.add('show');
    loadStickers(currentStickerTab);
});

closeStickerModal.addEventListener('click', () => {
    stickerModal.classList.remove('show');
    stickerGrid.innerHTML = '';
});

userStickersTab.addEventListener('click', () => {
    currentStickerTab = 'user';
    userStickersTab.classList.add('active');
    commonStickersTab.classList.remove('active');
    loadStickers('user');
});

commonStickersTab.addEventListener('click', () => {
    currentStickerTab = 'common';
    commonStickersTab.classList.add('active');
    userStickersTab.classList.remove('active');
    loadStickers('common');
});

stickerInput.addEventListener('change', async () => {
    if (stickerInput.files.length > 0) {
        const file = stickerInput.files[0];
        const formData = new FormData();
        formData.append('sticker', file);
        try {
            const response = await fetch('/upload_sticker', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.success) {
                loadStickers('user');
                stickerInput.value = '';
            } else {
                alert('Ошибка загрузки стикера: ' + data.message);
            }
        } catch (error) {
            console.error('Sticker upload error:', error);
            alert('Ошибка загрузки стикера');
        }
    }
});

async function loadStickers(tab) {
    try {
        const response = await fetch('/stickers');
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        const data = await response.json();
        stickerGrid.innerHTML = '';
        const stickers = tab === 'user' ? data.user_stickers : data.common_stickers;
        stickers.forEach(sticker => {
            const img = document.createElement('img');
            img.src = sticker.path;
            img.className = 'sticker w-[100px] h-[100px] object-contain rounded-lg';
            img.alt = sticker.filename;
            img.addEventListener('click', () => {
                sendSticker(sticker.path);
            });
            stickerGrid.appendChild(img);
        });
    } catch (error) {
        console.error('Load stickers error:', error);
        alert('Ошибка загрузки стикеров');
    }
}

function sendSticker(stickerPath) {
    if (!currentRecipient && !currentGroupId) return;
    socket.emit('send_message', {
        recipient: currentRecipient,
        group_id: currentGroupId,
        message: '',
        file: stickerPath,
        sticker: true,
        reply_to_id: replyToMessage ? replyToMessage.id : null
    });
    stickerModal.classList.remove('show');
    stickerGrid.innerHTML = '';
    clearReply.click();
}

async function addStickerToCollection(stickerPath) {
    try {
        const response = await fetch('/copy_sticker', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stickerPath })
        });
        const data = await response.json();
        if (data.success) {
            alert('Стикер добавлен в вашу коллекцию');
        } else {
            alert('Ошибка при добавлении стикера: ' + data.message);
        }
    } catch (error) {
        console.error('Copy sticker error:', error);
        alert('Ошибка при добавлении стикера');
    }
}

// Profile Handlers
profileLink.addEventListener('click', async () => {
    try {
        const response = await fetch(`/profile/${currentUser}`);
        const data = await response.json();
        if (data.success) {
            profileFullName.value = data.profile.full_name || '';
            profilePosition.value = data.profile.position || '';
            profileDepartment.value = data.profile.department || '';
            profileEmail.value = data.profile.email || '';
            profilePhone.value = data.profile.phone_number || '';
            if (data.profile.avatar_path) {
                profileAvatarPreview.src = data.profile.avatar_path;
                profileAvatarPreview.classList.remove('hidden');
            } else {
                profileAvatarPreview.classList.add('hidden');
            }
            profileEditModal.classList.add('show');
        } else {
            alert('Failed to load profile');
        }
    } catch (error) {
        console.error('Profile load error:', error);
        alert('Error loading profile');
    }
});

profileAvatarInput.addEventListener('change', () => {
    if (profileAvatarInput.files.length > 0) {
        const file = profileAvatarInput.files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            profileAvatarPreview.src = e.target.result;
            profileAvatarPreview.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    } else {
        profileAvatarPreview.classList.add('hidden');
    }
});

cancelProfileEdit.addEventListener('click', () => {
    profileEditModal.classList.remove('show');
    profileForm.reset();
    profileAvatarPreview.classList.add('hidden');
    profileAvatarInput.value = '';
});

profileForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('full_name', profileFullName.value || '');
    formData.append('position', profilePosition.value || '');
    formData.append('department', profileDepartment.value || '');
    formData.append('email', profileEmail.value || '');
    formData.append('phone_number', profilePhone.value || '');
    let avatarPath = '';
    if (profileAvatarInput.files.length > 0) {
        try {
            const avatarFormData = new FormData();
            avatarFormData.append('avatar', profileAvatarInput.files[0]);
            const avatarResponse = await fetch('/upload_avatar', {
                method: 'POST',
                body: avatarFormData
            });
            const avatarData = await avatarResponse.json();
            if (avatarData.success) {
                avatarPath = avatarData.avatarPath;
            } else {
                console.error('Avatar upload failed:', avatarData.message);
                alert('Failed to upload avatar: ' + avatarData.message);
                return;
            }
        } catch (error) {
            console.error('Avatar upload error:', error);
            alert('Error uploading avatar');
            return;
        }
    }
    formData.append('avatar_path', avatarPath);
    try {
        const response = await fetch('/profile', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            profileEditModal.classList.remove('show');
            profileForm.reset();
            profileAvatarPreview.classList.add('hidden');
            profileAvatarInput.value = '';
            refreshChats();
        } else {
            alert('Failed to update profile: ' + data.message);
        }
    } catch (error) {
        console.error('Profile update error:', error);
        alert('Error updating profile');
    }
});

async function showProfileView(username) {
    try {
        const response = await fetch(`/profile/${username}`);
        const data = await response.json();
        if (data.success) {
            profileViewUsername.textContent = username;
            profileViewFullName.textContent = data.profile.full_name || 'N/A';
            profileViewPosition.textContent = data.profile.position || 'N/A';
            profileViewDepartment.textContent = data.profile.department || 'N/A';
            profileViewEmail.textContent = data.profile.email || 'N/A';
            profileViewPhone.textContent = data.profile.phone_number || 'N/A';
            profileViewAvatar.src = data.profile.avatar_path || '/static/images/default-avatar.png';
            profileViewModal.classList.add('show');
        } else {
            alert('Profile not found');
        }
    } catch (error) {
        console.error('Profile view error:', error);
        alert('Error loading profile');
    }
}

closeProfileView.addEventListener('click', () => {
    profileViewModal.classList.remove('show');
});

// Logout Handler
logoutBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/logout', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            window.location.href = '/';
        }
    } catch (error) {
        console.error('Logout error:', error);
    }
});

// File Upload Handlers
fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        previewFileName.textContent = file.name;
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImage.src = e.target.result;
                previewImage.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        } else {
            previewImage.classList.add('hidden');
        }
        filePreview.classList.add('show');
    } else {
        filePreview.classList.remove('show');
        previewImage.classList.add('hidden');
        previewFileName.textContent = '';
    }
});

clearFile.addEventListener('click', () => {
    fileInput.value = '';
    filePreview.classList.remove('show');
    previewImage.classList.add('hidden');
    previewFileName.textContent = '';
});

// Reply Handlers
clearReply.addEventListener('click', () => {
    replyToMessage = null;
    replyPreview.classList.remove('show');
    replyMessage.textContent = '';
});

// Group Creation Handlers
createGroupBtn.addEventListener('click', () => {
    groupModal.classList.add('show');
    groupNameInput.focus();
});

groupSearch.addEventListener('input', async () => {
    const query = groupSearch.value;
    try {
        const response = await fetch(`/search?query=${query}`);
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        const users = await response.json();
        groupUserList.innerHTML = '';
        for (const user of users) {
            const profileResponse = await fetch(`/profile/${user}`);
            const profile = await profileResponse.json();
            const avatar = profile.success && profile.profile.avatar_path ? profile.profile.avatar_path : '/static/images/default-avatar.png';
            const li = document.createElement('li');
            li.className = 'p-2 hover:bg-gray-100 flex items-center space-x-3';
            li.innerHTML = `
                <input type="checkbox" class="group-checkbox" value="${user}" ${selectedGroupMembers.includes(user) ? 'checked' : ''}>
                <img src="${avatar}" class="w-8 h-8 rounded-full object-cover cursor-pointer" onclick="showProfileView('${user}')">
                <p class="font-semibold cursor-pointer" onclick="showProfileView('${user}')">${user}</p>
            `;
            li.querySelector('.group-checkbox').addEventListener('change', (e) => {
                if (e.target.checked) {
                    selectedGroupMembers.push(user);
                } else {
                    selectedGroupMembers = selectedGroupMembers.filter(u => u !== user);
                }
            });
            groupUserList.appendChild(li);
        }
    } catch (error) {
        console.error('Group search error:', error);
    }
});

createGroup.addEventListener('click', () => {
    const groupName = groupNameInput.value.trim();
    if (groupName && selectedGroupMembers.length > 0) {
        socket.emit('create_group', {
            group_name: groupName,
            members: selectedGroupMembers
        });
        groupModal.classList.remove('show');
        groupNameInput.value = '';
        groupSearch.value = '';
        groupUserList.innerHTML = '';
        selectedGroupMembers = [];
    } else {
        alert('Please enter a group name and select at least one member.');
    }
});

cancelGroup.addEventListener('click', () => {
    groupModal.classList.remove('show');
    groupNameInput.value = '';
    groupSearch.value = '';
    groupUserList.innerHTML = '';
    selectedGroupMembers = [];
});

// Group Participant Handlers
addParticipantBtn.addEventListener('click', () => {
    addParticipantSearch.classList.toggle('hidden');
    addParticipantList.classList.toggle('hidden');
    addParticipantSearch.focus();
});

addParticipantSearch.addEventListener('input', async () => {
    const query = addParticipantSearch.value;
    try {
        const response = await fetch(`/search?query=${query}`);
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        const users = await response.json();
        addParticipantList.innerHTML = '';
        socket.emit('get_group_members', { group_id: currentGroupId });
        socket.once('members_loaded', async (data) => {
            const currentMembers = data.members.map(m => m.username);
            for (const user of users) {
                if (!currentMembers.includes(user)) {
                    const profileResponse = await fetch(`/profile/${user}`);
                    const profile = await profileResponse.json();
                    const avatar = profile.success && profile.profile.avatar_path ? profile.profile.avatar_path : '/static/images/default-avatar.png';
                    const li = document.createElement('li');
                    li.className = 'p-2 hover:bg-gray-100 cursor-pointer flex items-center space-x-3';
                    li.innerHTML = `
                        <img src="${avatar}" class="w-8 h-8 rounded-full object-cover cursor-pointer" onclick="showProfileView('${user}')">
                        <p class="font-semibold cursor-pointer" onclick="showProfileView('${user}')">${user}</p>
                    `;
                    li.onclick = (e) => {
                        if (!e.target.closest('img') && !e.target.closest('p')) {
                            socket.emit('add_group_member', { group_id: currentGroupId, username: user });
                            addParticipantSearch.classList.add('hidden');
                            addParticipantList.classList.add('hidden');
                            addParticipantSearch.value = '';
                            addParticipantList.innerHTML = '';
                        }
                    };
                    addParticipantList.appendChild(li);
                }
            }
        });
    } catch (error) {
        console.error('Add participant search error:', error);
    }
});

closeParticipants.addEventListener('click', () => {
    participantsModal.classList.remove('show');
    participantsList.innerHTML = '';
    addParticipantSearch.classList.add('hidden');
    addParticipantList.classList.add('hidden');
    adminOnlyToggleContainer.classList.add('hidden');
    addParticipantSearch.value = '';
    addParticipantList.innerHTML = '';
});

// Socket Event Handlers
socket.on('connect', () => {
    refreshChats();
});

socket.on('group_created', (data) => {
    refreshChats();
    selectChat(null, data.group_id, data.group_name);
});

socket.on('members_loaded', async (data) => {
    participantsList.innerHTML = '';
    const isAdminOrCreator = data.members.some(m => m.username === currentUser && m.is_admin) || data.creator === currentUser;

    addParticipantBtn.classList.toggle('hidden', !isAdminOrCreator);
    adminOnlyToggleContainer.classList.toggle('hidden', !isAdminOrCreator);

    adminOnlyToggle.checked = data.admin_only_messages;
    adminOnlyToggle.onclick = () => {
        socket.emit('set_admin_only_messages', { group_id: data.group_id, enabled: adminOnlyToggle.checked });
    };

    for (const member of data.members) {
        const response = await fetch(`/user_status?username=${member.username}`);
        const status = await response.json();
        const profileResponse = await fetch(`/profile/${member.username}`);
        const profile = await profileResponse.json();
        const avatar = profile.success && profile.profile.avatar_path ? profile.profile.avatar_path : '/static/images/default-avatar.png';
        const li = document.createElement('li');
        li.className = 'p-2 flex items-center justify-between';
        li.innerHTML = `
            <div class="flex items-center space-x-3">
                <img src="${avatar}" class="w-8 h-8 rounded-full object-cover cursor-pointer" onclick="showProfileView('${member.username}')">
                <p class="font-semibold cursor-pointer" onclick="showProfileView('${member.username}')">${member.username}${member.is_admin ? ' (Админ)' : ''}${member.username === data.creator ? ' (Владелец)' : ''}</p>
                <span class="w-3 h-3 rounded-full ${status.online ? 'bg-green-500' : 'bg-gray-500'} border-2 border-white"></span>
            </div>
            <button class="participant-menu-btn text-xs text-gray-500 hover:text-indigo-600" title="Menu">
                <i class="fas fa-ellipsis-v"></i>
            </button>
            <div class="participant-menu absolute bg-white shadow-lg rounded-lg p-2 hidden z-10">
                <button class="write-btn block w-full text-left px-2 py-1 text-sm text-gray-700 hover:bg-gray-100">Написать</button>
                ${isAdminOrCreator && member.username !== currentUser ? `
                    <button class="delete-participant-btn block w-full text-left px-2 py-1 text-sm text-red-600 hover:bg-gray-100">Удалить</button>
                    ${data.creator === currentUser ? `
                        ${member.is_admin ? `
                            <button class="revoke-admin-btn block w-full text-left px-2 py-1 text-sm text-gray-700 hover:bg-gray-100">Удалить админ права</button>
                        ` : `
                            <button class="appoint-admin-btn block w-full text-left px-2 py-1 text-sm text-gray-700 hover:bg-gray-100">Назначить админом</button>
                        `}
                    ` : ''}
                ` : ''}
            </div>
        `;
        participantsList.appendChild(li);

        const menuBtn = li.querySelector('.participant-menu-btn');
        const menu = li.querySelector('.participant-menu');
        if (menuBtn && menu) {
            menuBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                document.querySelectorAll('.participant-menu.show').forEach(m => {
                    if (m !== menu) m.classList.remove('show');
                });
                menu.classList.toggle('show');
            });

            document.addEventListener('click', (e) => {
                if (!menu.contains(e.target) && !menuBtn.contains(e.target)) {
                    menu.classList.remove('show');
                }
            });
        }

        const writeBtn = li.querySelector('.write-btn');
        if (writeBtn) {
            writeBtn.addEventListener('click', () => {
                selectChat(member.username, null, member.username);
                participantsModal.classList.remove('show');
                participantsList.innerHTML = '';
                addParticipantSearch.classList.add('hidden');
                addParticipantList.classList.add('hidden');
                adminOnlyToggleContainer.classList.add('hidden');
                menu.classList.remove('show');
            });
        }

        const deleteBtn = li.querySelector('.delete-participant-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                socket.emit('remove_group_member', { group_id: data.group_id, username: member.username });
                menu.classList.remove('show');
            });
        }

        const appointBtn = li.querySelector('.appoint-admin-btn');
        if (appointBtn) {
            appointBtn.addEventListener('click', () => {
                socket.emit('appoint_admin', { group_id: data.group_id, username: member.username });
                menu.classList.remove('show');
            });
        }

        const revokeBtn = li.querySelector('.revoke-admin-btn');
        if (revokeBtn) {
            revokeBtn.addEventListener('click', () => {
                socket.emit('revoke_admin', { group_id: data.group_id, username: member.username });
                menu.classList.remove('show');
            });
        }
    }
    participantsModal.classList.add('show');
});

socket.on('members_updated', (data) => {
    if (data.group_id === currentGroupId) {
        socket.emit('get_group_members', { group_id: data.group_id });
    }
    refreshChats();
});

socket.on('error', (data) => {
    if (data.message === 'Unauthorized') {
        window.location.href = '/';
    } else {
        alert(data.message);
    }
});

// Search Handlers
searchInput.addEventListener('input', async () => {
    const query = searchInput.value;
    if (query.trim() === '') {
        refreshChats();
        return;
    }
    try {
        const response = await fetch(`/search?query=${query}`);
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        const users = await response.json();
        const statusResponse = await fetch('/user_status');
        const statuses = await statusResponse.json();
        chatList.innerHTML = '';
        lastChatList = [];
        for (const user of users) {
            const status = statuses.find(s => s.username === user) || { online: false };
            const profileResponse = await fetch(`/profile/${user}`);
            const profile = await profileResponse.json();
            const avatar = profile.success && profile.profile.avatar_path ? profile.profile.avatar_path : '/static/images/default-avatar.png';
            const li = document.createElement('li');
            li.className = 'p-4 hover:bg-gray-100 cursor-pointer flex items-center space-x-3';
            li.innerHTML = `
                <div class="relative">
                    <img src="${avatar}" class="w-10 h-10 rounded-full object-cover">
                    <span class="absolute bottom-0 right-0 w-3 h-3 rounded-full ${status.online ? 'bg-green-500' : 'bg-gray-500'} border-2 border-white"></span>
                </div>
                <div class="flex-1">
                    <p class="font-semibold">${user}</p>
                </div>
            `;
            li.onclick = () => {
                selectChat(user);
            };
            chatList.appendChild(li);
            lastChatList.push({ username: user, is_group: false });
        }
    } catch (error) {
        console.error('Search error:', error);
    }
});

// Chat Selection
async function selectChat(username, group_id, group_name) {
    if (isLoadingMessages) {
        console.log('Messages are already loading, skipping selectChat');
        return;
    }
    currentRecipient = username;
    currentGroupId = group_id;
    const headerText = group_id ? group_name : username;
    const icon = group_id ? 'fa-users' : 'fa-user';
    let statusText = group_id ? 'Групповой чат' : 'Нет в сети';
    let statusClass = 'bg-gray-500';
    let avatar = '/static/images/default-avatar.png';
    if (username) {
        const response = await fetch(`/user_status?username=${username}`);
        const status = await response.json();
        statusText = status.online ? 'В сети' : 'Нет в сети';
        statusClass = status.online ? 'bg-green-500' : 'bg-gray-500';
        const profileResponse = await fetch(`/profile/${username}`);
        const profile = await profileResponse.json();
        if (profile.success && profile.profile.avatar_path) {
            avatar = profile.profile.avatar_path;
        }
    }
    chatHeader.innerHTML = `
        <div class="flex items-center ${username ? 'cursor-pointer' : ''}" ${username ? `onclick="showProfileView('${username}')"` : ''}>
            ${group_id ? `
                <div class="w-12 h-12 rounded-full bg-gray-300 flex items-center justify-center mr-3">
                    <i class="fas ${icon} text-xl text-gray-600"></i>
                </div>
            ` : `
                <div class="relative mr-3">
                    <img src="${avatar}" class="w-12 h-12 rounded-full object-cover">
                    <span class="absolute bottom-0 right-0 w-3 h-3 rounded-full ${statusClass} border-2 border-white"></span>
                </div>
            `}
            <div>
                <h3 class="font-semibold ${group_id ? 'cursor-pointer hover:text-indigo-600' : ''}" ${group_id ? 'onclick="showGroupParticipants(' + group_id + ')"' : ''}>${headerText}</h3>
                <p class="text-sm text-gray-500">${statusText}</p>
            </div>
        </div>
    `;
    messagesDiv.innerHTML = '';
    isLoadingMessages = true;
    socket.emit('load_messages', { recipient: username, group_id });
    socket.emit('mark_as_read', { recipient: username, group_id });
}

function showGroupParticipants(group_id) {
    socket.emit('get_group_members', { group_id });
}

// Chat List Updates
socket.on('chats_loaded', async (chats) => {
    const uniqueChats = [];
    const seen = new Set();
    for (const chat of chats) {
        const key = chat.is_group ? `group_${chat.group_id}` : chat.username;
        if (!seen.has(key)) {
            seen.add(key);
            uniqueChats.push(chat);
        }
    }

    const currentKeys = lastChatList.map(c => c.is_group ? `group_${c.group_id}` : c.username);
    const newKeys = uniqueChats.map(c => c.is_group ? `group_${c.group_id}` : c.username);
    if (currentKeys.sort().join() === newKeys.sort().join()) {
        return;
    }

    lastChatList = uniqueChats.map(c => ({
        username: c.username,
        group_id: c.group_id,
        group_name: c.group_name,
        is_group: c.is_group,
        unread_count: c.unread_count
    }));

    const statusResponse = await fetch('/user_status');
    const statuses = await statusResponse.json();
    chatList.innerHTML = '';
    for (const chat of uniqueChats) {
        const status = chat.username ? (statuses.find(s => s.username === chat.username) || { online: false }) : null;
        const profileResponse = chat.username ? await fetch(`/profile/${chat.username}`) : null;
        const profile = profileResponse ? await profileResponse.json() : null;
        const avatar = chat.username && profile && profile.success && profile.profile.avatar_path ? profile.profile.avatar_path : '/static/images/default-avatar.png';
        const li = document.createElement('li');
        li.className = 'p-4 hover:bg-gray-100 cursor-pointer flex items-center space-x-3';
        li.innerHTML = `
            ${chat.is_group ? `
                <div class="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center">
                    <i class="fas fa-users text-gray-600"></i>
                </div>
            ` : `
                <div class="relative">
                    <img src="${avatar}" class="w-10 h-10 rounded-full object-cover">
                    <span class="absolute bottom-0 right-0 w-3 h-3 rounded-full ${status && status.online ? 'bg-green-500' : 'bg-gray-500'} border-2 border-white"></span>
                </div>
            `}
            <div class="flex-1 flex justify-between items-center">
                <p class="font-semibold">${chat.is_group ? chat.group_name : chat.username}</p>
                ${chat.unread_count > 0 ? `<span class="bg-red-500 text-white text-xs rounded-full px-2 py-1">${chat.unread_count}</span>` : ''}
            </div>
        `;
        li.onclick = () => {
            selectChat(chat.is_group ? null : chat.username, chat.is_group ? chat.group_id : null, chat.is_group ? chat.group_name : null);
        };
        chatList.appendChild(li);
    }
});

socket.on('update_chats', (data) => {
    if (data.recipient === currentUser || (data.group_id && currentGroupId === data.group_id)) {
        refreshChats();
    }
});

// Message Handling
socket.on('messages_loaded', (messages) => {
    console.log('Messages loaded:', messages.map(m => ({ id: m.id, timestamp: m.timestamp })));
    messagesDiv.innerHTML = '';
    messages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    messages.forEach(msg => {
        addMessage(msg.id, msg.sender, msg.message, msg.timestamp, msg.is_read, msg.file, msg.forwarded_from, msg.group_id, msg.reply_to_id, msg.sticker, false);
    });
    isLoadingMessages = false;
});

socket.on('receive_message', (data) => {
    console.log('Received message:', { id: data.id, timestamp: data.timestamp });
    if ((data.recipient === currentRecipient && !data.group_id) || data.group_id === currentGroupId) {
        const placeholder = messagesDiv.querySelector('.message-placeholder');
        if (placeholder) {
            placeholder.remove();
        }
        addMessage(data.id, data.sender, data.message, data.timestamp, data.is_read, data.file, data.forwarded_from, data.group_id, data.reply_to_id, data.sticker, true);
        socket.emit('mark_as_read', { recipient: data.sender, group_id: data.group_id });
    }
    if ((data.recipient !== currentRecipient && !data.group_id) || (data.group_id && data.group_id !== currentGroupId)) {
        refreshChats();
    }
});

socket.on('update_read_status', (data) => {
    if ((data.recipient === currentUser && data.sender === currentRecipient && !data.group_id) || data.group_id === currentGroupId) {
        document.querySelectorAll('.message').forEach(msg => {
            if (msg.dataset.sender === currentUser && msg.dataset.isRead === '0') {
                msg.dataset.isRead = '1';
                const status = msg.querySelector('.read-status');
                if (status) status.innerHTML = '<i class="fas fa-check-double text-indigo-200"></i>';
            }
        });
    }
});

socket.on('message_deleted', (data) => {
    const messageElement = document.querySelector(`.message[data-message-id="${data.message_id}"]`);
    if (messageElement) {
        messageElement.remove();
    }
});

// Forward Message Handlers
forwardSearch.addEventListener('input', async () => {
    const query = forwardSearch.value;
    try {
        const response = await fetch(`/search?query=${query}`);
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        const users = await response.json();
        const chatsResponse = await fetch('/chats');
        if (chatsResponse.status === 401) {
            window.location.href = '/';
            return;
        }
        const chats = await chatsResponse.json();
        const statusResponse = await fetch('/user_status');
        const statuses = await statusResponse.json();
        forwardUserList.innerHTML = '';

        for (const user of users) {
            if (user !== currentRecipient) {
                const status = statuses.find(s => s.username === user) || { online: false };
                const profileResponse = await fetch(`/profile/${user}`);
                const profile = await profileResponse.json();
                const avatar = profile.success && profile.profile.avatar_path ? profile.profile.avatar_path : '/static/images/default-avatar.png';
                const li = document.createElement('li');
                li.className = `p-2 hover:bg-gray-100 cursor-pointer flex items-center space-x-3 ${selectedForwardUsers.includes(user) ? 'bg-indigo-100' : ''}`;
                li.innerHTML = `
                    <img src="${avatar}" class="w-8 h-8 rounded-full object-cover cursor-pointer" onclick="showProfileView('${user}')">
                    <p class="font-semibold cursor-pointer" onclick="showProfileView('${user}')">${user}</p>
                    <span class="w-3 h-3 rounded-full ${status.online ? 'bg-green-500' : 'bg-gray-500'} border-2 border-white"></span>
                `;
                li.onclick = (e) => {
                    if (!e.target.closest('img') && !e.target.closest('p')) {
                        if (selectedForwardUsers.includes(user)) {
                            selectedForwardUsers = selectedForwardUsers.filter(u => u !== user);
                            li.classList.remove('bg-indigo-100');
                        } else {
                            selectedForwardUsers.push(user);
                            li.classList.add('bg-indigo-100');
                        }
                    }
                };
                forwardUserList.appendChild(li);
            }
        }

        chats.filter(chat => chat.is_group).forEach(chat => {
            const groupIdentifier = `group_${chat.group_id}`;
            if (chat.group_id !== currentGroupId) {
                const li = document.createElement('li');
                li.className = `p-2 hover:bg-gray-100 cursor-pointer flex items-center space-x-3 ${selectedForwardUsers.includes(groupIdentifier) ? 'bg-indigo-100' : ''}`;
                li.innerHTML = `
                    <div class="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center">
                        <i class="fas fa-users text-sm text-gray-600"></i>
                    </div>
                    <p class="font-semibold">${chat.group_name}</p>
                `;
                li.onclick = () => {
                    if (selectedForwardUsers.includes(groupIdentifier)) {
                        selectedForwardUsers = selectedForwardUsers.filter(u => u !== groupIdentifier);
                        li.classList.remove('bg-indigo-100');
                    } else {
                        selectedForwardUsers.push(groupIdentifier);
                        li.classList.add('bg-indigo-100');
                    }
                };
                forwardUserList.appendChild(li);
            }
        });
    } catch (error) {
        console.error('Forward search error:', error);
    }
});

sendForward.addEventListener('click', () => {
    if (selectedForwardUsers.length > 0 && messageToForward) {
        socket.emit('forward_message', {
            new_recipients: selectedForwardUsers,
            message: messageToForward.message,
            file: messageToForward.file,
            forwarded_from: messageToForward.sender,
            sticker: messageToForward.sticker || false
        });
        forwardModal.classList.remove('show');
        forwardSearch.value = '';
        forwardUserList.innerHTML = '';
        selectedForwardUsers = [];
        messageToForward = null;
    }
});

cancelForward.addEventListener('click', () => {
    forwardModal.classList.remove('show');
    forwardSearch.value = '';
    forwardUserList.innerHTML = '';
    selectedForwardUsers = [];
    messageToForward = null;
});

// Message Submission
messageForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentRecipient && !currentGroupId) return;

    const placeholder = document.createElement('div');
    placeholder.className = 'p-2 flex justify-end message-placeholder';
    placeholder.innerHTML = `
        <div class="inline-block p-3 rounded-lg bg-indigo-300 text-white max-w-md">
            <p class="text-sm italic">Sending...</p>
        </div>
    `;
    messagesDiv.appendChild(placeholder);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('recipient', currentRecipient || '');
        formData.append('group_id', currentGroupId || '');

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            if (response.status === 401) {
                window.location.href = '/';
                return;
            }
            const data = await response.json();
            if (data.success) {
                socket.emit('send_message', {
                    recipient: currentRecipient,
                    group_id: currentGroupId,
                    message: file.name,
                    file: data.filePath,
                    reply_to_id: replyToMessage ? replyToMessage.id : null,
                    sticker: false
                });
                clearReply.click();
            }
            fileInput.value = '';
            filePreview.classList.remove('show');
            previewImage.classList.add('hidden');
            previewFileName.textContent = '';
        } catch (error) {
            console.error('File upload error:', error);
            placeholder.remove();
            alert('Failed to upload file.');
        }
    } else if (messageInput.value.trim()) {
        socket.emit('send_message', {
            recipient: currentRecipient,
            group_id: currentGroupId,
            message: messageInput.value,
            reply_to_id: replyToMessage ? replyToMessage.id : null,
            sticker: false
        });
        messageInput.value = '';
        clearReply.click();
    }
});

// Message Rendering
async function addMessage(id, sender, message, timestamp, is_read, file = null, forwarded_from = null, group_id = null, reply_to_id = null, sticker = false, isNewMessage = false) {
    if (id && document.querySelector(`.message[data-message-id="${id}"]`)) {
        console.log(`Message ${id} already exists, skipping`);
        return;
    }

    const profileResponse = await fetch(`/profile/${sender}`);
    const profile = await profileResponse.json();
    const avatar = profile.success && profile.profile.avatar_path ? profile.profile.avatar_path : '/static/images/default-avatar.png';
    const div = document.createElement('div');
    const isOwnMessage = sender === currentUser;
    div.className = `p-2 flex ${isOwnMessage ? 'justify-end' : 'justify-start'} message message-animation`;
    div.dataset.sender = sender;
    div.dataset.isRead = is_read;
    div.dataset.timestamp = timestamp;
    if (id) div.dataset.messageId = id;

    let content = '';
    if (sticker && file) {
        content += `<img src="${file}" class="w-[30px] h-[30px] object-contain rounded-lg" style="width: 150px; height: 150px;" alt="Sticker">`;
    } else if (file) {
        const fileExtension = file.split('.').pop().toLowerCase();
        if (['jpg', 'jpeg', 'png', 'gif'].includes(fileExtension)) {
            content += `<a href="${file}" target="_blank"><img src="${file}" class="max-w-xs rounded-lg" alt="${message}"></a>`;
        } else {
            content += `<a href="${file}" target="_blank" class="${isOwnMessage ? 'text-white' : 'text-indigo-500'} hover:underline"><i class="fas fa-file mr-2"></i>${message}</a>`;
        }
    } else {
        content += message;
    }

    let replyContent = '';
    if (reply_to_id) {
        const replyMessageElement = document.querySelector(`.message[data-message-id="${reply_to_id}"]`);
        if (replyMessageElement) {
            const replySender = replyMessageElement.dataset.sender;
            const replyText = replyMessageElement.querySelector('p:not(.text-xs)')?.textContent || '';
            replyContent = `
                <div class="reply-preview p-2 mb-2 rounded bg-white border-l-4 border-indigo-400">
                    <p class="text-xs text-black font-semibold">${replySender}</p>
                    <p class="text-sm text-black truncate">${replyText}</p>
                </div>
            `;
        }
    }

    const senderLabel = group_id && !isOwnMessage ? `
        <p class="text-xs ${isOwnMessage ? 'text-indigo-100' : 'text-gray-600'} font-semibold cursor-pointer" onclick="showProfileView('${sender}')">${sender}</p>
    ` : '';
    const forwardedLabel = forwarded_from ? `<p class="text-xs ${isOwnMessage ? 'text-indigo-100' : 'text-gray-500'} italic">Forwarded from ${forwarded_from}</p>` : '';

    div.innerHTML = `
        <div class="flex items-start space-x-2">
            ${!isOwnMessage ? `
                <img src="${avatar}" class="w-8 h-8 rounded-full object-cover cursor-pointer mt-3" onclick="showProfileView('${sender}')">
            ` : ''}
            <div class="inline-block p-3 rounded-lg ${isOwnMessage ? 'bg-indigo-500 text-white' : 'bg-white text-gray-800'} max-w-md relative">
                ${senderLabel}
                ${forwardedLabel}
                ${replyContent}
                <p>${content}</p>
                <div class="flex items-center justify-between mt-1">
                    <span class="text-xs ${isOwnMessage ? 'text-indigo-100' : 'text-gray-500'}">${new Date(timestamp).toLocaleTimeString()}</span>
                    ${isOwnMessage ? `<span class="read-status text-xs">${is_read ? '<i class="fas fa-check-double text-indigo-200"></i>' : '<i class="fas fa-check text-indigo-200"></i>'}</span>` : ''}
                </div>
                <button class="menu-btn text-xs ${isOwnMessage ? 'text-indigo-100' : 'text-gray-500'} hover:text-indigo-300" aria-label="Message options">
                    <i class="fas fa-ellipsis-v"></i>
                </button>
                <div class="message-menu absolute top-8 right-2 bg-white shadow-lg rounded-lg p-2 hidden z-10">
                    <button class="forward-btn block w-full text-left px-2 py-1 text-sm text-gray-700 hover:bg-gray-100">Переслать</button>
                    <button class="reply-btn block w-full text-left px-2 py-1 text-sm text-gray-700 hover:bg-gray-100">Ответить</button>
                    ${sticker ? `<button class="add-sticker-btn block w-full text-left px-2 py-1 text-sm text-gray-700 hover:bg-gray-100">Добавить в свои стикеры</button>` : ''}
                    ${isOwnMessage ? `<button class="delete-btn block w-full text-left px-2 py-1 text-sm text-red-600 hover:bg-gray-100">Удалить</button>` : ''}
                </div>
            </div>
        </div>
    `;

    // Вставка сообщения
    if (isNewMessage) {
        // Новые сообщения добавляются в конец
        messagesDiv.appendChild(div);
        console.log(`Added new message ${id} with timestamp ${timestamp} at end`);
    } else {
        // Исторические сообщения вставляются с учётом timestamp
        const existingMessages = Array.from(messagesDiv.querySelectorAll('.message'));
        let inserted = false;
        for (let i = 0; i < existingMessages.length; i++) {
            const existingTimestamp = existingMessages[i].dataset.timestamp;
            if (new Date(timestamp) < new Date(existingTimestamp)) {
                messagesDiv.insertBefore(div, existingMessages[i]);
                inserted = true;
                console.log(`Inserted message ${id} with timestamp ${timestamp} before ${existingTimestamp}`);
                break;
            }
        }
        if (!inserted) {
            messagesDiv.appendChild(div);
            console.log(`Added message ${id} with timestamp ${timestamp} at end (no earlier messages)`);
        }
    }
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    const menuBtn = div.querySelector('.menu-btn');
    const menu = div.querySelector('.message-menu');
    if (menuBtn && menu) {
        menuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.message-menu.show').forEach(m => {
                if (m !== menu) m.classList.remove('show');
            });
            menu.classList.toggle('show');
        });

        document.addEventListener('click', (e) => {
            if (!menu.contains(e.target) && !menuBtn.contains(e.target)) {
                menu.classList.remove('show');
            }
        });
    } else {
        console.error(`Menu button or menu not found for message ${id}`);
    }

    const forwardBtn = div.querySelector('.forward-btn');
    if (forwardBtn) {
        forwardBtn.addEventListener('click', () => {
            messageToForward = { sender, message, file, sticker };
            forwardModal.classList.add('show');
            forwardSearch.focus();
            menu.classList.remove('show');
        });
    }

    const replyBtn = div.querySelector('.reply-btn');
    if (replyBtn) {
        replyBtn.addEventListener('click', () => {
            replyToMessage = { id, sender, message };
            replyMessage.textContent = `${sender}: ${message.substring(0, 50)}${message.length > 50 ? '...' : ''}`;
            replyPreview.classList.add('show');
            messageInput.focus();
            menu.classList.remove('show');
        });
    }

    const addStickerBtn = div.querySelector('.add-sticker-btn');
    if (addStickerBtn) {
        addStickerBtn.addEventListener('click', () => {
            addStickerToCollection(file);
            menu.classList.remove('show');
        });
    }

    const deleteBtn = div.querySelector('.delete-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', () => {
            if (id) {
                socket.emit('delete_message', { message_id: id });
                menu.classList.remove('show');
            }
        });
    }
}