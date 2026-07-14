<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { usePosts } from '../stores/posts'
import PostEditor from '../components/PostEditor.vue'
import type { Post } from '../api'

const store = usePosts()
const editing = ref<Post | null>(null)
const dialog = ref(false)

onMounted(store.load)

function open(p: Post | null) { editing.value = p; dialog.value = true }
async function save(body: Omit<Post, 'id' | 'created_at' | 'updated_at'>) {
  await store.save(body, editing.value?.id)
  dialog.value = false
}
</script>

<template>
  <div>
    <el-button type="primary" @click="open(null)">게시물 작성</el-button>

    <el-table :data="store.list" style="margin-top: 16px">
      <el-table-column prop="title" label="제목" />
      <el-table-column label="템플릿">
        <template #default="{ row }">{{ store.templateById(row.template_id)?.name }}</template>
      </el-table-column>
      <el-table-column label="">
        <template #default="{ row }">
          <el-button link @click="open(row)">수정</el-button>
          <el-button link type="danger" @click="store.remove(row.id)">삭제</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="editing ? '게시물 수정' : '게시물 작성'" width="980px">
      <PostEditor v-if="dialog" :key="String(editing?.id ?? 'new')"
                  :templates="store.templates" :post="editing" @save="save" />
    </el-dialog>
  </div>
</template>
