let currentObjectURL = null;
let currentVideoElement = null;
let hls = null; // 将 Hls 实例移到全局作用域

// 监听页面是否加载完成
document.addEventListener("DOMContentLoaded", () => {
  //页面加载完成后，如果存在up_go按钮，则开始监听相应表单
  if (document.getElementById("up_go")) {
    initializeFormValidation();
  }

  //页面加载完成后，如果存在previewModal弹窗，则执行相应方法
  if (document.getElementById("previewModal")) {
    closePreviewFile();
  }
});

function initializeFormValidation() {
  const upGoButton = document.getElementById("up_go");
  upGoButton.addEventListener("mouseover", validateForm);
}

//上传页面用于校验表单信息
function validateForm(event) {
  const missingFields = [];

  // 获取表单字段值并检查
  const album = document.getElementById("inputAlbum").value.trim();
  const subject = document.getElementById("inputSubject").value.trim();
  const category = document.getElementById("categorySelect").value;
  const level = document.getElementById("levelSelect").value;

  // 检查必填字段
  if (!album) missingFields.push("专辑不能为空");
  if (!subject) missingFields.push("标题不能为空");
  if (!category || category === "选择分类......")
    missingFields.push("请选择分类");
  if (!level || level === "选择文件等级") missingFields.push("请选择文件等级");

  // 如果有未填写的字段，阻止表单提交并提示用户
  if (missingFields.length > 0) {
    alert(missingFields.join(", "));
    console.log("表单校验失败，缺少字段: " + missingFields.join(", "));
  } else {
    console.log("表单校验通过");
  }
}

function closePreviewFile() {
  // 监听模态框隐藏事件以撤销 Object URL 和销毁 Hls 实例
  document
    .getElementById("previewModal")
    .addEventListener("hidden.bs.modal", () => {
      // 如果 currentObjectURL 存在，则移除
      if (currentObjectURL) {
        URL.revokeObjectURL(currentObjectURL);
        currentObjectURL = null; // 清除保存的 URL
      }

      // 确保视频暂停播放
      if (currentVideoElement) {
        currentVideoElement.pause();
        currentVideoElement.src = ""; // 清除 src 属性
        currentVideoElement = null;
      }

      // 销毁 Hls 实例
      if (hls) {
        hls.destroy();
        hls = null; // 清除保存的 Hls 实例
      }
    });
}

//预览文件
async function previewFile(md5, mime) {
  //获取弹窗元素
  const modalBody = document.querySelector("#previewModal .modal-body");
  //定义从后端获取数据路径
  const url = `${window.location.origin}/files/data/${md5}/`;
  //获取文件信息（其中含文件块的数据链接）
  try {
    // 获取文件元数据
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error("获取文件元数据失败: " + response.statusText);
    }
    const data = await response.json(); // 解析 JSON 数据

    // 根据 MIME 类型创建预览内容
    let content;
    //先判断是否为图片，如果为图片，则开始下载图片数据，并创建加载对象
    if (mime.startsWith("image/")) {
      //下载文件数据并创建 Blob 对象
      const blob = await fetchChunks(data.fileDatas, mime);
      //先撤销上一个 Object URL（如果存在）
      if (currentObjectURL) {
        URL.revokeObjectURL(currentObjectURL);
      }
      //创建新的 Object URL
      currentObjectURL = URL.createObjectURL(blob);
      //开始写样式数据
      content = `<img src="${currentObjectURL}" id="${md5}" class="img-fluid" alt="${data.fileName}">`;
    }

    //如果视频已转换为HLS视频流，则优先采用HLS视频流播放
    else if (mime.startsWith("video/") && data.hlsAddr?.endsWith("m3u8")) {
      content = `<video id="${md5}" controls class="w-100">HLS流播放器</video>`;
    }

    //先判断是否为大小<1G的视频，若为真，则开始下载视频数据，并创建加载对象
    else if (
      mime.startsWith("video/") &&
      data.fileSize < 1073741824 &&
      !data.hlsAddr?.endsWith("m3u8")
    ) {
      //下载文件数据并创建 Blob 对象
      const blob = await fetchChunks(data.fileDatas, mime);
      //先撤销上一个 Object URL（如果存在）
      if (currentObjectURL) {
        URL.revokeObjectURL(currentObjectURL);
      }
      //创建新的 Object URL
      currentObjectURL = URL.createObjectURL(blob);
      //开始写样式数据
      content = `<video src="${currentObjectURL}" id="${md5}" controls class="w-100">
                 <source type="${mime}"></video>`;
    }

    //先判断是否为大小>1G的视频，若为真，则提示文件过大，下载后再进行观看
    else if (
      mime.startsWith("video/") &&
      data.fileSize > 1073741824 &&
      !data.hlsAddr?.endsWith("m3u8")
    ) {
      content = `<h2>视频文件太大，请下载后观看！</h2>`;
    }
    //若为其他类型，则提示无法预览该文件类型
    else {
      content = `<h2>无法预览该文件类型。</h2>`;
    }

    // 清理旧内容并注入新内容
    modalBody.innerHTML = content;

    // 显示模态框
    const previewModal = new bootstrap.Modal(
      document.getElementById("previewModal")
    );
    previewModal.show();

    //如果采用HLS视频流播放，则加载支持播放的hls的js方法
    if (mime.startsWith("video/") && data.hlsAddr?.endsWith("m3u8")) {
      playEncryptedHLS(md5, data.hlsAddr);
      currentVideoElement = document.getElementById(md5);
    }
  } catch (error) {
    // console.error("文件预览错误:", error);
    modalBody.innerHTML = `<p class='h4'>无法预览该文件: ${error.message}</p>`;

    // 显示模态框
    const previewModal = new bootstrap.Modal(
      document.getElementById("previewModal")
    );
    previewModal.show();
  }
}

// 下载文件（下载完后合并）
async function downloadFile(md5, mime) {
  //获取弹窗元素
  const modalBody = document.querySelector("#previewModal .modal-body");
  // 构造获取文件元数据的 URL
  const url = `${window.location.origin}/files/data/${md5}/`;

  try {
    // 获取文件元数据
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`获取文件元数据失败: ${response.statusText}`);
    }
    const data = await response.json(); // 解析 JSON 数据

    // 请求用户提供保存位置
    const handle = await window.showSaveFilePicker({
      suggestedName: data.fileName, // 使用文件名
      types: [
        {
          description: mime,
          accept: { [mime]: [data.fileType] }, // 根据 MIME 类型和文件扩展名设置
        },
      ],
    });

    // 创建可写流
    const writable = await handle.createWritable();

    try {
      // 逐块下载并写入文件
      for (const dataUrl of data.fileDatas) {
        // 确保 URL 是完整的
        const blockUrl = new URL(dataUrl, window.location.origin).toString();
        const response = await fetch(blockUrl);
        if (!response.ok) {
          throw new Error(
            `从 ${blockUrl} 下载数据块失败: ${response.statusText}`
          );
        }

        // 读取响应流并写入文件
        const reader = response.body.getReader();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          await writable.write(value); // 写入数据块
        }
      }

      // 完成写入
      await writable.close();

      modalBody.innerHTML = `<p class='h4'>文件下载完成！</p>`;
      // 显示模态框
      const previewModal = new bootstrap.Modal(
        document.getElementById("previewModal")
      );
      previewModal.show();
    } catch (error) {
      modalBody.innerHTML = `<p class='h5'>下载文件出错，请检查: ${error}</p>`;
      // 显示模态框
      const previewModal = new bootstrap.Modal(
        document.getElementById("previewModal")
      );
      previewModal.show();
      await writable.abort(); // 发生错误时中止写入
    }
  } catch (error) {
    modalBody.innerHTML = `<p class='h5'>下载文件出错，请检查: ${error}</p>`;
    // 显示模态框
    const previewModal = new bootstrap.Modal(
      document.getElementById("previewModal")
    );
    previewModal.show();
  }
}

//获取文件块数据
async function fetchChunks(urls, mime) {
  const chunkSize = 5; // 每次下载5个块
  const chunks = [];

  for (let i = 0; i < urls.length; i += chunkSize) {
    const batch = urls.slice(i, i + chunkSize); // 分批下载
    const responses = await Promise.all(
      batch.map(async (url) => {
        // 确保 URL 是完整的
        const blockUrl = new URL(url, window.location.origin).toString();
        const response = await fetch(blockUrl);
        if (!response.ok) {
          throw new Error(`下载数据块失败: ${response.statusText}`);
        }
        return response.arrayBuffer();
      })
    );
    chunks.push(...responses);
  }

  // 合并数据块为 Blob 对象
  return new Blob(chunks, { type: mime });
}

//播放HLS视频流
function playEncryptedHLS(elementID, hlsAddr) {
  const video = document.getElementById(elementID);

  // 检查 Hls.js 是否被支持
  if (Hls.isSupported()) {
    if (hls) {
      // 如果 Hls 实例已经存在，则销毁它
      try {
        hls.destroy();  // 不再使用 .then()，因为 destroy() 是同步方法
      } catch (error) {
        console.error("销毁 Hls 实例时出错:", error);
      }
      initializeHLS(video, hlsAddr); // 重新初始化 Hls 实例
    } else {
      initializeHLS(video, hlsAddr); // 如果 Hls 实例不存在，直接初始化
    }
  } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
    // 对于不支持 Hls.js 的浏览器，使用原生播放 HLS `${window.location.origin}/files/data/${md5}/`;
    video.src = `${window.location.origin}/${hlsAddr}`;
    video.addEventListener("loadedmetadata", () => {
      video.play().catch((error) => {
        console.error("播放视频时出错:", error);
      });
    });
  } else {
    console.error("HLS 播放器不受支持");
  }
}

// 初始化 Hls 实例
function initializeHLS(video, hlsAddr) {
  hls = new Hls();

  // 监听 Hls 事件
  hls.on(Hls.Events.ERROR, function (event, data) {
    console.error("Hls.js 错误:", data);
  });

  hls.loadSource(`${window.location.origin}/${hlsAddr}`);
  hls.attachMedia(video);

  hls.on(Hls.Events.MEDIA_ATTACHED, function () {
    console.log("视频与 Hls.js 绑定成功！");
    video.play().catch((error) => {
      console.error("播放视频时出错:", error);
    });
  });

  hls.on(Hls.Events.ERROR, function (event, data) {
    if (data.fatal === Hls.ErrorTypes.NETWORK_ERROR) {
      console.error("Hls 网络错误:", data);
    } else if (data.fatal === Hls.ErrorTypes.MEDIA_ERROR) {
      console.error("Hls 媒体错误:", data);
    } else if (data.fatal === Hls.ErrorTypes.OTHER_ERROR) {
      console.error("Hls 其他错误:", data);
    }
  });
}

async function deleteFile(md5) {
  //获取弹窗元素
  const modalBody = document.querySelector("#previewModal .modal-body");
  // 构造获取文件元数据的 URL
  const url = `${window.location.origin}/files/delete/${md5}`;

  try {
    // 获取文件元数据
    const response = await fetch(url);
    // 判断是否请求成功
    if (!response.ok) {
      throw new Error(`删除文件源数据失败: ${response.statusText}`);
    }
    // 将请求的数据赋值给data
    const data = await response.json(); // 解析 JSON 数据
    // 将请求返回的数据显示在弹窗中
    modalBody.innerHTML = `<p class='h4'>${data.content}</p>`;
    // 显示模态框
    const previewModal = new bootstrap.Modal(
      document.getElementById("previewModal")
    );
    previewModal.show();
  } catch (error) {
    modalBody.innerHTML = `<p class='h5'>删除文件出错，请检查: ${error}</p>`;
    // 显示模态框
    const previewModal = new bootstrap.Modal(
      document.getElementById("previewModal")
    );
    previewModal.show();
  }
}

async function editFileInfo(md5, name, album, subject) {
  //将现有信息赋值到表单
  document.getElementById("name").value = name;
  document.getElementById("album").value = album;
  document.getElementById("subject").value = subject;
  
  // 显示更新文件信息的模态窗口
  const modal = new bootstrap.Modal(document.getElementById("editFileInfo"));
  modal.show();

  // 获取页面上的CSRF令牌，以确保POST请求的安全性
  const csrfMetaTag = document.querySelector('meta[name="csrf-token"]');
  let csrfToken = null;

  if (csrfMetaTag) {
    csrfToken = csrfMetaTag.getAttribute("content");
    console.log("CSRF Token:", csrfToken); // 在控制台中输出CSRF令牌（仅用于调试）
  } else {
    console.error("CSRF meta tag not found!");
    return; // 如果没有找到CSRF令牌，则返回
  }

  // 获取操作表单元素
  const form = document.getElementById("fileInfoForm");

  // 确保表单只绑定一次事件处理程序
  form.addEventListener("submit", handleFormSubmit);

  async function handleFormSubmit(event) {
    event.preventDefault(); // 防止表单的默认提交行为

    // 使用 FormData 自动处理表单字段
    const formData = new FormData(form);

    try {
      const response = await fetch(
        `${window.location.origin}/files/update/${md5}/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(`网络响应不正常: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.status === "successful") {
        alert(result.content);
        modal.hide(); // 隐藏模态窗口
        location.reload();
        // 这里可以添加刷新页面的内容或者其他操作
      } else {
        alert(result.content);
        // 处理表单错误，如显示错误信息
      }
    } catch (error) {
      alert("提交失败，请稍后重试。");
      console.error("提交错误:", error);
    }
  }
}
